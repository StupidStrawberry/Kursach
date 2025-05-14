#from crypto.crypto import encrypt_aes_256_gcm, decrypt_aes_256_gcm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os


def encrypt_aes_256_gcm(text: str, key: bytes = None, iv: bytes = None) -> tuple:
    """
    Шифрует строку с использованием AES-256-GCM.

    Args:
        text: Строка для шифрования.
        key: Ключ (32 байта). Если None — генерируется автоматически.
        iv: Вектор инициализации (12 байт). Если None — генерируется автоматически.

    Returns:
        tuple: (ciphertext, key, iv, tag) — зашифрованные данные в байтах, ключ, IV и тег.
    """
    data = text.encode('utf-8')  # конвертируем строку в байты

    if key is None:
        key = os.urandom(32)  # AES-256 ключ
    if iv is None:
        iv = os.urandom(12)  # IV для GCM

    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()

    return ciphertext, key, iv, encryptor.tag


def decrypt_aes_256_gcm(ciphertext: bytes, key: bytes, iv: bytes, tag: bytes) -> str:
    """
    Расшифровывает данные и возвращает исходную строку.

    Args:
        ciphertext: Зашифрованные данные (bytes).
        key: Ключ (32 байта).
        iv: Вектор инициализации (12 байт).
        tag: Тег аутентификации.

    Returns:
        str: Расшифрованная строка.
    """
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted_data.decode('utf-8')  # конвертируем байты обратно в строку


# Пример использования
if __name__ == "__main__":
    file = open("data.txt", 'r')

    encrypted_messages = []
    for line in file:
        ciphertext, key, iv, tag = encrypt_aes_256_gcm(line)
        encrypted_messages.append((ciphertext, key, iv, tag))
        ciphertext.hex()

    for i, (ciphertext, key, iv, tag) in enumerate(encrypted_messages, 1):
        decrypted_data = decrypt_aes_256_gcm(ciphertext, key, iv, tag)
        decrypted_text = decrypted_data

