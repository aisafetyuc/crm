import base64
import getpass
import hashlib
import os
import sys

def derive_key_from_passphrase(passphrase, project_identifier="crmsaltissaltyyes"):
    """
    Convert a human-readable passphrase into a cryptographic key.
    Uses a fixed project identifier instead of a random salt.
    """
    # Use a fixed, project-specific identifier instead of a random salt
    salt = project_identifier.encode('utf-8')
    
    # Use PBKDF2 to derive a key from the passphrase
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100000
    )
    
    return key

def encrypt_file(input_file, output_file, passphrase):
    """Encrypt a file using a passphrase."""
    # Read the file content
    with open(input_file, 'rb') as f:
        plaintext = f.read()
    
    # Derive a key from the passphrase
    key = derive_key_from_passphrase(passphrase)
    
    # Create a deterministic file-specific nonce based on original filename only
    # This ensures consistent nonce generation regardless of path
    original_filename = os.path.basename(input_file)
    file_nonce = hashlib.sha256((original_filename + "nonce").encode()).digest()[:16]
    
    # Create a keystream using the key and file-specific nonce
    keystream = b''
    temp = file_nonce
    while len(keystream) < len(plaintext):
        temp = hashlib.sha256(key + temp).digest()
        keystream += temp
    
    # Truncate the keystream to the plaintext length
    keystream = keystream[:len(plaintext)]
    
    # XOR the plaintext with the keystream
    encrypted = bytes(p ^ k for p, k in zip(plaintext, keystream))
    
    # Store the original filename in the encrypted file for reference during decryption
    # Format: [16 bytes filename length][filename bytes][encrypted data]
    filename_bytes = original_filename.encode('utf-8')
    filename_length = len(filename_bytes).to_bytes(16, byteorder='big')
    
    # Write the encrypted data with filename metadata
    with open(output_file, 'wb') as f:
        f.write(filename_length)
        f.write(filename_bytes)
        f.write(encrypted)
    
    print(f"File encrypted successfully: {output_file}")

def decrypt_file(input_file, output_file, passphrase):
    """Decrypt a file using a passphrase."""
    # Read the encrypted file
    with open(input_file, 'rb') as f:
        # Read the original filename metadata
        filename_length_bytes = f.read(16)
        filename_length = int.from_bytes(filename_length_bytes, byteorder='big')
        original_filename_bytes = f.read(filename_length)
        original_filename = original_filename_bytes.decode('utf-8')
        
        # Read the actual encrypted data
        encrypted = f.read()
    
    # Derive the key from the passphrase
    key = derive_key_from_passphrase(passphrase)
    
    # Create the same deterministic file-specific nonce using the stored original filename
    file_nonce = hashlib.sha256((original_filename + "nonce").encode()).digest()[:16]
    
    # Create a keystream using the key and file-specific nonce
    keystream = b''
    temp = file_nonce
    while len(keystream) < len(encrypted):
        temp = hashlib.sha256(key + temp).digest()
        keystream += temp
    
    # Truncate the keystream to the encrypted data length
    keystream = keystream[:len(encrypted)]
    
    # XOR the encrypted data with the keystream
    decrypted = bytes(e ^ k for e, k in zip(encrypted, keystream))
    
    # Write the decrypted data to the output file
    with open(output_file, 'wb') as f:
        f.write(decrypted)
    
    print(f"File decrypted successfully: {output_file}")

def process_directory(input_dir, output_dir, passphrase, mode, file_extension=".enc"):
    """
    Process all files in a directory (and subdirectories) for encryption or decryption.
    
    Args:
        input_dir: Source directory containing files to process
        output_dir: Destination directory for processed files
        passphrase: Passphrase for encryption/decryption
        mode: 'encrypt' or 'decrypt'
        file_extension: Extension to add/remove for encrypted files
    """
    # Make sure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Track processed files
    processed_count = 0
    
    # Walk through all files in the input directory and its subdirectories
    for root, dirs, files in os.walk(input_dir):
        # Create corresponding output subdirectory structure
        rel_path = os.path.relpath(root, input_dir)
        if rel_path == '.':
            rel_path = ''
        
        current_output_dir = os.path.join(output_dir, rel_path)
        if not os.path.exists(current_output_dir):
            os.makedirs(current_output_dir)
        
        # Process each file
        for file in files:
            input_file_path = os.path.join(root, file)
            
            # Skip the script itself if it happens to be in the directory
            if os.path.abspath(input_file_path) == os.path.abspath(sys.argv[0]):
                continue
                
            if mode == 'encrypt':
                # Skip already encrypted files
                if file.endswith(file_extension):
                    continue
                
                output_file_path = os.path.join(current_output_dir, file + file_extension)
                try:
                    encrypt_file(input_file_path, output_file_path, passphrase)
                    processed_count += 1
                except Exception as e:
                    print(f"Error encrypting {input_file_path}: {str(e)}")
                
            elif mode == 'decrypt':
                # Only process encrypted files
                if not file.endswith(file_extension):
                    continue
                
                # Remove the encryption extension for the output file
                output_file_name = file[:-len(file_extension)]
                output_file_path = os.path.join(current_output_dir, output_file_name)
                try:
                    decrypt_file(input_file_path, output_file_path, passphrase)
                    processed_count += 1
                except Exception as e:
                    print(f"Error decrypting {input_file_path}: {str(e)}")
    
    return processed_count

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  File mode:")
        print("    python script.py encrypt input_file output_file")
        print("    python script.py decrypt input_file output_file")
        print("  Directory mode:")
        print("    python script.py encrypt-dir input_directory output_directory [extension]")
        print("    python script.py decrypt-dir input_directory output_directory [extension]")
        print("\nDefault extension for encrypted files is '.enc'")
        return
    
    mode = sys.argv[1].lower()
    
    # Get passphrase from the user
    passphrase = getpass.getpass("Enter passphrase: ")
    
    # File mode
    if mode in ['encrypt', 'decrypt']:
        if len(sys.argv) < 4:
            print(f"Error: {mode} mode requires input and output file paths")
            return
            
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        
        if not os.path.exists(input_file):
            print(f"Error: Input file {input_file} not found")
            return
        
        if mode == 'encrypt':
            encrypt_file(input_file, output_file, passphrase)
        else:  # decrypt
            decrypt_file(input_file, output_file, passphrase)
    
    # Directory mode
    elif mode in ['encrypt-dir', 'decrypt-dir']:
        if len(sys.argv) < 4:
            print(f"Error: {mode} mode requires input and output directory paths")
            return
            
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        
        # Optional custom extension
        file_extension = ".enc"
        if len(sys.argv) > 4:
            file_extension = sys.argv[4]
            if not file_extension.startswith('.'):
                file_extension = '.' + file_extension
        
        if not os.path.exists(input_dir) or not os.path.isdir(input_dir):
            print(f"Error: Input directory {input_dir} not found or is not a directory")
            return
        
        # Extract the core mode from the directory mode command
        core_mode = 'encrypt' if mode == 'encrypt-dir' else 'decrypt'
        
        # Process the directory
        processed_count = process_directory(input_dir, output_dir, passphrase, core_mode, file_extension)
        print(f"Completed {core_mode}ion of {processed_count} files from {input_dir} to {output_dir}")
    
    else:
        print(f"Unknown mode: {mode}")
        print("Use 'encrypt', 'decrypt', 'encrypt-dir', or 'decrypt-dir'")

if __name__ == "__main__":
    main()
