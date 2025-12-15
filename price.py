from __future__ import division

import xml.etree.ElementTree as ET
import argparse
import json
import os

circuit_bill = {}
xml_root = None
detailed = False
library_roots = {}  # Cache para los XML roots de las librerías (key = nombre del circuito)
all_roots = []  # Lista de todos los roots cargados para buscar circuitos
base_path = ""  # Path base para resolver rutas relativas de librerías


def load_external_libraries(root, lib_base_path=None):
    """Carga las librerías externas referenciadas en el archivo .circ"""
    global library_roots
    global all_roots
    
    if lib_base_path is None:
        lib_base_path = base_path
    
    # Agregar este root a la lista de roots si no está ya
    if root not in all_roots:
        all_roots.append(root)
        
    for lib in root.findall("lib"):
        desc = lib.get("desc", "")
        if desc.startswith("file#"):
            # Es una librería externa
            lib_path = desc[5:]  # Quitar "file#"
            full_path = os.path.normpath(os.path.join(lib_base_path, lib_path))
            
            if full_path not in library_roots:  # Evitar cargar el mismo archivo dos veces
                if os.path.exists(full_path):
                    try:
                        lib_root = ET.parse(full_path).getroot()
                        library_roots[full_path] = lib_root
                        all_roots.append(lib_root)
                        # Cargar librerías anidadas recursivamente usando el directorio de esta librería
                        lib_dir = os.path.dirname(full_path)
                        load_external_libraries(lib_root, lib_dir)
                    except Exception as e:
                        print(f"Error loading library {lib_path}: {e}")
                else:
                    print(f"Library file not found: {full_path}")


def find_circuit_root(circuit_name):
    """Busca el root que contiene la definición de un circuito"""
    for root in all_roots:
        if root.find("./circuit[@name='{}']".format(circuit_name)) is not None:
            return root
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="The logisim file")
    parser.add_argument(
        "circuit_name", help="The name of the circuit to calculate the price."
    )
    parser.add_argument(
        "-d",
        "--detailed",
        help="Creates a more detailed price glossary.",
        action="store_true",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="The file to dump the prices to, if ommited it will print the result to the stdout.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=0,
        help="Fail if the component exceed the limit price.",
    )

    args = parser.parse_args()

    global xml_root
    global detailed
    global base_path
    global library_roots

    input_file = args.file  # "s-mips.circ"
    output_file = args.output  # "result.json"
    circuit_name = args.circuit_name  # "S-MIPS"
    ensure_limit = args.limit  # 100
    detailed = args.detailed  # False
    
    # Establecer el path base para resolver librerías
    base_path = os.path.dirname(os.path.abspath(input_file))

    xml_root = ET.parse(input_file).getroot()
    
    # Cargar las librerías externas
    load_external_libraries(xml_root)

    _main = xml_root.find("./circuit[@name='{}']".format(circuit_name))
    if _main is None:
        print("There is no circuit called {}".format(circuit_name))
        exit(1)

    get_circuit_info(_main)

    if output_file is None:
        print(json.dumps(circuit_bill, indent=4))
    else:
        json.dump(circuit_bill, open(output_file, "w"), indent=4)

    # Mostrar resumen del precio total
    total_price = circuit_bill[circuit_name]["price"]
    print(f"\n{'='*50}")
    print(f"PRECIO TOTAL DE '{circuit_name}': {total_price}")
    print(f"{'='*50}")

    if ensure_limit > 0 and ensure_limit < total_price:
        print(f"ERROR: El precio ({total_price}) excede el límite ({ensure_limit})")
        exit(1)


def bill(input_file, circuit_name):
    global xml_root
    global detailed
    global base_path
    global library_roots

    # Establecer el path base para resolver librerías
    base_path = os.path.dirname(os.path.abspath(input_file))
    
    xml_root = ET.parse(input_file).getroot()
    
    # Cargar las librerías externas
    load_external_libraries(xml_root)

    _main = xml_root.find("./circuit[@name='{}']".format(circuit_name))
    if _main is None:
        raise ValueError("There is no circuit called {}".format(circuit_name))

    get_circuit_info(_main)

    return circuit_bill


def get_circuit_info(comp, level=0):
    if level > 100:
        exit(1)
    if is_default(comp):
        return get_default_circuit_info(comp)
    
    circuit_name = comp.get("name")
    
    # print("\t"*level + circuit_name)

    # Si ya procesamos este circuito, devolver su precio (se incrementa amount en el padre)
    if circuit_name in circuit_bill:
        circuit_bill[circuit_name]["amount"] += 1
        return {"price": circuit_bill[circuit_name]["price"]}

    # Buscar el root que contiene este circuito
    search_root = find_circuit_root(circuit_name)
    if search_root is None:
        print(f"Circuit not found: {circuit_name}")
        return {"price": 0}

    price = 0
    parts = search_root.findall("./circuit[@name='{}']/comp".format(circuit_name))
    parts.extend(search_root.findall("./circuit[@name='{}']/wire".format(circuit_name)))

    circuit_bill[circuit_name] = {"price": 0, "amount": 1, "parts": {}}

    for c in parts:
        info = get_circuit_info(c, level + 1)
        part_price = info["price"]
        price += part_price
        comp_id = get_comp_id(c)[1]
        if comp_id in circuit_bill[circuit_name]["parts"]:
            circuit_bill[circuit_name]["parts"][comp_id]["amount"] += 1
            if detailed:
                circuit_bill[circuit_name]["parts"][comp_id]["units"].append(info)
            circuit_bill[circuit_name]["parts"][comp_id]["total cost"] += part_price
        else:
            data = {"amount": 1, "total cost": part_price}
            if detailed:
                data["units"] = [info]
            circuit_bill[circuit_name]["parts"][comp_id] = data

    circuit_bill[circuit_name]["price"] = price
    return {"price": price}


def is_default(comp):
    """Determina si un componente es un componente predefinido de Logisim o un wire"""
    if comp.tag == "wire":
        return True
    lib_id = comp.get("lib")
    if lib_id is None:
        return False
    # Las librerías 0-6 son las incorporadas de Logisim
    # Las librerías 7+ son librerías externas (circuitos personalizados)
    try:
        return int(lib_id) <= 6
    except ValueError:
        return False


def get_comp_id(comp):
    if is_default(comp):
        if comp.tag == "wire":
            key = ("0", "Wire")
        else:
            key = (comp.get("lib"), comp.get("name"))
    else:
        key = ("-1", comp.get("name"))

    return key


def get_default_circuit_info(comp):
    key = get_comp_id(comp)
    if comp.tag == "wire":
        info = {"from": comp.get("from"), "to": comp.get("to")}
    else:
        info = {}
        for prop in comp.findall("a"):
            info[prop.get("name")] = prop.get("val")

    info["price"] = calculate_price(key, info)

    return info


def calculate_price(key, info):
    def get_value(key, val):
        return int(info.get(key, val))

    price = 0

    if key == ("0", "Wire"):
        price = 0
    elif key == ("6", "Text"):
        price = 0
    elif key == ("0", "Splitter"):
        price = 0
    elif key == ("0", "Tunnel"):
        price = 0
    elif key == ("0", "Pin"):
        price = 1 if "pull" in info else 0
    elif key == ("0", "Probe"):
        price = 0
    elif key == ("0", "Pull Resistor"):
        price = 0
    elif key == ("0", "Clock"):
        price = 1
    elif key == ("0", "Constant"):
        price = 0
    elif key == ("0", "Power"):
        price = 0
    elif key == ("0", "Ground"):
        price = 0
    elif key == ("0", "Transistor"):
        price = 2
    elif key == ("0", "Transmission Gate"):
        price = 4
    elif key == ("0", "Bit Extender"):
        price = get_value("in_width", 8) + get_value("out_width", 16)

    elif key == ("1", "NOT Gate"):
        w = get_value("width", 1)
        price = 2 * w
    elif key == ("1", "Buffer"):
        w = get_value("width", 1)
        price = 2 * w
    elif key == ("1", "AND Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w
    elif key == ("1", "OR Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w
    elif key == ("1", "NAND Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w + 2 * w
    elif key == ("1", "NOR Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w + 2 * w
    elif key == ("1", "XOR Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w
    elif key == ("1", "XNOR Gate"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 1) * w + 2 * w
    elif key == ("1", "Odd Parity"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 4) * w
    elif key == ("1", "Even Parity"):
        w = get_value("width", 1)
        price = (get_value("inputs", 5) + 4) * w
    elif key == ("1", "Controlled Buffer"):
        w = get_value("width", 1)
        price = 3 * w
    elif key == ("1", "Controlled Inverter"):
        w = get_value("width", 1)
        price = 3 * w

    elif key == ("2", "Multiplexer"):
        w = get_value("width", 1)
        s = get_value("select", 1)
        price = (2**s - 1) * w * 10
    elif key == ("2", "Demultiplexer"):
        w = get_value("width", 1)
        s = get_value("select", 1)
        price = (2**s - 1) * w * 7
    elif key == ("2", "Decoder"):
        s = get_value("select", 1)
        price = 3 * s**2 - s
    elif key == ("2", "Priority Encoder"):
        s = get_value("select", 3)
        n = 2**s
        price = n**2 + 3 * n + s * n // 2
    elif key == ("2", "BitSelector"):
        w = get_value("width", 8)
        o = get_value("group", 1)
        price = w + o

    elif key == ("3", "Adder"):
        w = get_value("width", 8)
        price = 4 * w
    elif key == ("3", "Subtractor"):
        w = get_value("width", 8)
        price = 4 * w
    elif key == ("3", "Multiplier"):
        w = get_value("width", 8)
        price = 4 * w**2
    elif key == ("3", "Divider"):
        w = get_value("width", 8)
        price = 4 * w**2
    elif key == ("3", "Negator"):
        w = get_value("width", 8)
        price = 2 * w
    elif key == ("3", "Comparator"):
        w = get_value("width", 8)
        price = 16 + 4 * w
    elif key == ("3", "Shifter"):
        w = get_value("width", 8)
        price = w**2
    elif key == ("3", "BitAdder"):
        w = get_value("width", 8)
        price = 4 * w
    elif key == ("3", "BitFinder"):
        w = get_value("width", 8)
        price = 4 * w

    elif key == ("4", "D Flip-Flop"):
        price = 24
    elif key == ("4", "T Flip-Flop"):
        price = 12
    elif key == ("4", "J-K Flip-Flop"):
        price = 12
    elif key == ("4", "S-R Flip-Flop"):
        price = 6
    elif key == ("4", "Register"):
        w = get_value("width", 8)
        price = 24 * w
    elif key == ("4", "Counter"):
        w = get_value("width", 8)
        price = 28 * w
    elif key == ("4", "Shift Register"):
        w = get_value("width", 1)
        price = 40 * w
    elif key == ("4", "Random"):
        w = get_value("width", 8)
        price = 5 * w
    elif key == ("4", "RAM"):
        a = get_value("addrWidth", 8)
        w = get_value("dataWidth", 8)
        price = 2**a * w * 8
    elif key == ("4", "ROM"):
        a = get_value("addrWidth", 8)
        w = get_value("dataWidth", 8)
        price = 2**a * w * 0.5

    elif key == ("5", "Button"):
        price = 2
    elif key == ("5", "Joystick"):
        price = 3000
    elif key == ("5", "Keyboard"):
        price = 3000
    elif key == ("5", "LED"):
        price = 10
    elif key == ("5", "7-Segment Display"):
        price = 100
    elif key == ("5", "Hex Digit Display"):
        price = 100
    elif key == ("5", "DotMatrix"):
        c = get_value("matrixcols", 5)
        r = get_value("matrixrows", 7)
        price = c * r * 0.01
    elif key == ("5", "TTY"):
        c = get_value("cols", 32)
        r = get_value("rows", 8)
        price = c * r * 0.05
    else:
        print("Unknown element {}".format(key))

    return price


if __name__ == "__main__":
    main()
