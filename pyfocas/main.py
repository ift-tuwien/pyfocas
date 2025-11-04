"""Test functionality of library"""

from pyfocas.protocol.protocol import FOCAS


def main():
    """Communicate with machine using FOCAS library"""

    focas = FOCAS(hostname="localhost", port=8193)
    print(focas.connect())
    print(focas.get_sys_info())
    print(focas.get_status_info())
    macros = focas.read_macro(502)
    value_502 = macros[502]
    print(f"old value: {value_502}")
    focas.write_macro_double(502, 100)
    print(focas.read_macro(502))
    focas.write_macro_double(502, value_502)
    print(focas.read_macro(502))


if __name__ == "__main__":
    main()
