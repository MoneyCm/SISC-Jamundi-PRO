"""Cifrado de las copias de seguridad del SISC para guardarlas fuera del computador (Drive institucional).

Cifrado híbrido: cada copia se cifra con una clave AES-256-GCM al azar, y esa clave se cifra con la
LLAVE PÚBLICA RSA-4096 que vive en este computador. Solo la LLAVE PRIVADA (que guarda la Secretaría
fuera del computador) puede abrir las copias.

Uso:
  python respaldo_cifrado.py llaves   <carpeta_publica> <archivo_privada>   # una sola vez
  python respaldo_cifrado.py cifrar   <copia.dump> <llave_publica.pem> <salida.cifrado>
  python respaldo_cifrado.py descifrar <copia.cifrado> <llave_privada.pem> <salida.dump>

Formato del archivo cifrado: b"SISC1" + largo de la clave cifrada (2 bytes) + clave cifrada
+ nonce (12 bytes) + datos cifrados con su etiqueta de autenticidad.
"""
import os
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MARCA = b"SISC1"
OAEP = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def crear_llaves(carpeta_publica: str, archivo_privada: str) -> None:
    privada = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    os.makedirs(carpeta_publica, exist_ok=True)
    with open(os.path.join(carpeta_publica, "llave_publica_respaldo.pem"), "wb") as salida:
        salida.write(privada.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo))
    with open(archivo_privada, "wb") as salida:
        salida.write(privada.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))


def cifrar(origen: str, llave_publica: str, destino: str) -> None:
    with open(llave_publica, "rb") as archivo:
        publica = serialization.load_pem_public_key(archivo.read())
    clave, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    with open(origen, "rb") as archivo:
        datos = AESGCM(clave).encrypt(nonce, archivo.read(), MARCA)
    clave_cifrada = publica.encrypt(clave, OAEP)
    temporal = destino + ".parcial"
    with open(temporal, "wb") as salida:
        salida.write(MARCA + len(clave_cifrada).to_bytes(2, "big") + clave_cifrada + nonce + datos)
    os.replace(temporal, destino)  # el archivo final solo aparece completo


def descifrar(origen: str, llave_privada: str, destino: str) -> None:
    with open(llave_privada, "rb") as archivo:
        privada = serialization.load_pem_private_key(archivo.read(), password=None)
    with open(origen, "rb") as archivo:
        contenido = archivo.read()
    if not contenido.startswith(MARCA):
        raise ValueError("El archivo no es una copia cifrada del SISC.")
    largo = int.from_bytes(contenido[5:7], "big")
    clave = privada.decrypt(contenido[7:7 + largo], OAEP)
    nonce = contenido[7 + largo:19 + largo]
    with open(destino, "wb") as salida:
        salida.write(AESGCM(clave).decrypt(nonce, contenido[19 + largo:], MARCA))


if __name__ == "__main__":
    accion, *argumentos = sys.argv[1:]
    {"llaves": crear_llaves, "cifrar": cifrar, "descifrar": descifrar}[accion](*argumentos)
