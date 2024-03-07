from cryptography.fernet import Fernet

KEY = Fernet.generate_key()


# Function to encrypt a message
def encrypt_message(message: str) -> str:
    # Convert the message into bytes
    bytes_message = message.encode()
    # Create a Fernet object with the provided key
    f = Fernet(KEY)
    # Encrypt the message
    encrypted_message = f.encrypt(bytes_message)

    return encrypted_message.decode()


# Function to decrypt a message
def decrypt_message(encrypted_message: str) -> str:
    # Create a Fernet object with the provided key
    f = Fernet(KEY)
    # Decrypt the message
    decrypted_message = f.decrypt(encrypted_message)
    # Decode the bytes back into a string
    return decrypted_message.decode()
