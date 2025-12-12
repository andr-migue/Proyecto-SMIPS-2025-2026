import os
import subprocess
import optparse

import unittest

verbose_level = 0
verbose_level_all = 4
verbose_level_compile_detail = 3
verbose_level_test_detail = 2
verbose_level_test_basic_detail = 1


def print_verbose(verbose_level_required: int, *args):
    if verbose_level >= verbose_level_required:
        print(*args)


class TestCase:
    def __init__(
        self,
        test_name: str,
        file: str,
        expected_result: str | None,
        expected_speed: int | None = None,
    ):
        self.file = file
        self.expected_result = expected_result
        self.expected_speed = expected_speed
        self.test_name = test_name
        self.runned = False
        self.failed = False
        self.error = False

    def run(self, logisim: str, circ: str, template: str) -> None:
        # result = ""
        cmd = [
            logisim,
            template,
            "-tty",
            "halt,tty,speed",
            "-load",
            self.file,
            "-sub",
            template,
            circ,
        ]
        try:
            print_verbose(
                verbose_level_test_detail, "Ejecutando el test: ", self.test_name
            )
            result = subprocess.run(cmd, stdout=subprocess.PIPE)
            self.runned = True
            if result.returncode != 0:
                print("Error al ejecutar test: ", self.test_name)
                print(result.stdout)
                print(result.stderr)
                self.error = True
                self.failed = True
                return
            output = bytes.decode(result.stdout)
            r = output.find("halted due to halt pin")
            self.result = output[:r].strip()
            s = output.find("Hz (")
            e = output.find(" ticks", s)
            self.speed = int(output[s + 4 : e])

            self.failed = self.result != self.expected_result or (
                self.expected_speed != None and self.speed > self.expected_speed
            )

        except subprocess.CalledProcessError as e:
            print("Error al ejecutar test: ", self.test_name)
            print(result.stdout)
            print(result.stderr)
            self.error = True
            self.failed = True

    def print(self) -> None:
        if self.error:
            print("El test no pudo ejecutarse correctamente")

        elif self.runned:
            status = self.result == self.expected_result
            print(
                "Resultado:",
                self.test_name,
                " ===============================================> ",
                "OK" if status else "FAIL",
            )
            print_verbose(
                verbose_level_test_detail,
                "Resultado Esperado: ",
                self.expected_result,
                "Resultado Obtenido: ",
                self.result,
            )
            if self.expected_speed != None:
                status = self.speed <= self.expected_speed
                print(
                    "Tiempo:",
                    self.test_name,
                    " ===============================================> ",
                    "OK" if status else "FAIL",
                )
                print_verbose(
                    verbose_level_test_detail,
                    "Tiempo Esperado: ",
                    self.expected_speed,
                    "Tiempo Obtenido: ",
                    self.speed,
                )
            else:
                print_verbose(
                    verbose_level_test_detail,
                    "Tiempo Obtenido: ",
                    self.speed,
                )

        else:
            print("Test:", self.test_name, "Debe correr el test antes")

        print(
            "---------------------------------------------------------------------------------------"
        )


class TestSuite:
    def __init__(self, dir: str, base_dir: str, circ: str, template: str, logisim: str, python: str):
        self.base_dir = base_dir
        self.circ = circ
        self.path = dir
        self.test: list[TestCase] = []
        self.template = template
        self.logisim = logisim
        self.python = python
        self.failed: bool = False

    def setup(self, fn:str|None = None):
        for file, path in self.searchAsmFiles():
            if fn is not None and file != fn:
                continue
            self.compile(file, path)
            expected = self.extractExpectedResult(path)
            excepted_time = self.extractExpectedSpeed(path)
            self.test.append(
                TestCase(
                    file,
                    os.path.join(self.base_dir, file, "Bank"),
                    expected,
                    excepted_time,
                )
            )

    def searchAsmFiles(self):
        for root, _, files in os.walk(self.path):
            print_verbose(verbose_level_all, "Buscando archivos .asm en: ", root)
            for file in files:
                try:
                    if file.endswith(".asm"):
                        print_verbose(verbose_level_all, "Archivo encontrado: ", file)
                        path = os.path.join(root, file)
                        yield file[:-4], path
                except Exception as e:
                    print("e")

    def compile(self, file: str, path: str) -> None:
        base_dir = os.path.join(self.base_dir, file)
        print_verbose(verbose_level_all, "Creando directorio: ", base_dir)
        try:
            os.mkdir(base_dir)
        except FileExistsError as e:
            print_verbose(verbose_level_all, "Directorio existente: ", base_dir)
        print_verbose(verbose_level_all, "Compilando: ", path)
        status = os.system(f"{self.python} assembler.py {path} -o {base_dir}")
        if status != 0:
            print("Error al compilar: ", path)

    def extractExpectedResult(self, path: str) -> str | None:
        with open(path, "r") as file:
            content = file.readlines()

        expected = None

        for line in content:
            if line.startswith("#prints"):
                expected = line[8:].strip()
                break
        else:
            return None
        print_verbose(verbose_level_all, "Resultado esperado del test: ")
        print_verbose(verbose_level_all, expected)
        return expected

    def extractExpectedSpeed(self, path: str) -> int | None:
        with open(path, "r") as file:
            content = file.readlines()

        expected = None

        for line in content:
            if line.startswith("#limit"):
                expected = int(line[7:].strip())
                break
        else:
            return None
        print_verbose(verbose_level_all, "Tiempo esperado del test: ")
        print_verbose(verbose_level_all, expected)
        return expected

    def run_all(self) -> None:
        for test in self.test:
            test.run(self.logisim, self.circ, self.template)
            self.failed |= test.failed
            test.print()

    def run_test(self, test_name: str):
        self.setup(test_name)
        for test in self.test:
            if test.test_name == test_name:
                test.run(self.logisim, self.circ, self.template)
                self.failed |= test.failed
                test.print()
                return test


class LogisimTests(unittest.TestCase):

    def setUp(self):
        global test_suite
        self.tests = test_suite

    def check(self, name:str):
        test = self.tests.run_test(name)
        self.assertFalse(test.failed, f"Expected: {test.expected_result} | Got: {test.result}")

    def test_add(self):
        self.check('add')
    def test_addi(self):
        self.check('addi')
    def test_and(self):
        self.check('and')
    def test_andi(self):
        self.check('andi')
    def test_beq(self):
        self.check('beq')
    def test_bgtz(self):
        self.check('bgtz')
    def test_blez(self):
        self.check('blez')
    def test_bltz(self):
        self.check('bltz')
    def test_bne(self):
        self.check('bne')
    def test_code(self):
        self.check('code')
    def test_div_mult_bne(self):
        self.check('div-mult-bne')
    def test_div(self):
        self.check('div')
    def test_divu_mulu_bne(self):
        self.check('divu-mulu-bne')
    def test_divu(self):
        self.check('divu')
    def test_halt(self):
        self.check('halt')
    def test_hello(self):
        self.check('hello')
    def test_jmp(self):
        self.check('jmp')
    def test_lemp(self):
        self.check('lemp')
    def test_liset(self):
        self.check('liset')
    def test_mcd(self):
        self.check('mcd')
    def test_mem(self):
        self.check('mem')
    def test_mult(self):
        self.check('mult')
    def test_mulu(self):
        self.check('mulu')
    def test_mycase(self):
        self.check('mycase')
    def test_nor(self):
        self.check('nor')
    def test_or(self):
        self.check('or')
    def test_ori(self):
        self.check('ori')
    def test_pop(self):
        self.check('pop')
    def test_push_pop(self):
        self.check('push-pop')
    def test_push(self):
        self.check('push')
    def test_rnd(self):
        self.check('rnd')
    def test_slt(self):
        self.check('slt')
    def test_slti(self):
        self.check('slti')
    def test_sub(self):
        self.check('sub')
    def test_sw_lw(self):
        self.check('sw-lw')
    def test_sw_push_pop(self):
        self.check('sw-push-pop')
    def test_test(self):
        self.check('test')
    def test_tty(self):
        self.check('tty')
    def test_xor(self):
        self.check('xor')
    def test_xori(self):
        self.check('xori')

input_dir:str
circ:str
output_folder:str
template:str
python:str
logisim:str

usage = "usage: %prog tests_dir circuit [options]"

parser = optparse.OptionParser(usage=usage)
parser.add_option(
    "-o",
    "--out",
    dest="output_folder",
    type="string",
    default=".",
    help="Specify output folder to compile tests",
)
parser.add_option(
    "-t",
    "--template",
    dest="template",
    type="string",
    default="s-mips-template.circ",
    help="The template .circ file without specific implementation",
)
parser.add_option(
    "-v",
    "--verbose",
    dest="verbose",
    type="int",
    default=0,
    help="Verbose debug mode",
)
parser.add_option(
    "-l",
    "--logisim",
    dest="logisim",
    type="string",
    default="logisim",
    help="The logisim program or path to run tests",
)
parser.add_option(
    "-p",
    "--python",
    dest="python",
    type="string",
    default="python",
    help="The python program or path to compile tests",
)

unit = False

try:
    options, args = parser.parse_args()
    if len(args) != 3:
        raise ValueError()
    input_dir = args[0]
    circ = args[1]
    output_folder = options.output_folder
    template = options.template
    verbose_level = int(options.verbose)
    python = options.python
    logisim = options.logisim
except:
    input_dir = os.getenv('TESTS', '')
    circ = os.getenv('CIRC', '')
    output_folder = os.getenv('OUT', '')
    template = os.getenv('TEMPLATE', '')
    verbose_level = int(os.getenv('VERBOSE', 0))
    python = os.getenv('PYTHON', '')
    logisim = os.getenv('LOGISIM', '')
    unit = True
    if not input_dir or not circ:
        parser.error("Incorrect command line arguments")
        exit(1)

try:
    os.mkdir(output_folder)
except FileExistsError as e:
    print_verbose(verbose_level_all, "Directorio existente: ", output_folder)

if not os.path.exists(template):
    print("El archivo de template no existe")
    exit(1)

test_suite = TestSuite(input_dir, output_folder, circ, template, logisim, python)

if __name__ == '__main__':
    if unit == True:
        unittest.main()
    else:
        test_suite.setup()
        test_suite.run_all()
        if test_suite.failed:
            exit(1)
