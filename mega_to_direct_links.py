#!/usr/bin/env python3
"""
MEGA Folder to Direct Links Converter
This script takes a MEGA folder URL and generates direct download links for all files within it.
"""

import re
import json
import requests
import base64
import struct
import sys
from Crypto.Cipher import AES

def base64_url_decode(data):
    """Decode base64-url string, adding padding if necessary."""
    data += '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data)

def base64_to_a32(s):
    """Convert base64 string to a32 (array of 32-bit integers)."""
    return str_to_a32(base64_url_decode(s))

def str_to_a32(b):
    """Convert byte string to a32."""
    if len(b) % 4:
        b += b'\0' * (4 - len(b) % 4)
    return struct.unpack('>%dI' % (len(b) / 4), b)

def a32_to_str(a):
    """Convert a32 to byte string."""
    return struct.pack('>%dI' % len(a), *a)

def aes_cbc_decrypt(data, key):
    """Decrypt data using AES-CBC with zero IV."""
    return AES.new(key, AES.MODE_CBC, b'\0' * 16).decrypt(data)

def decrypt_key(a, k):
    """Decrypt a node key using the folder/parent key."""
    res = []
    for i in range(0, len(a), 4):
        block = a[i:i+4]
        if len(block) == 4:
            res += str_to_a32(aes_cbc_decrypt(a32_to_str(block), a32_to_str(k)))
        else:
            res += block
    return tuple(res)

def decrypt_attr(attr, key):
    """Decrypt node attributes (metadata like filename)."""
    try:
        data = aes_cbc_decrypt(attr, a32_to_str(key))
        data = data.rstrip(b'\0')
        if not data.startswith(b'MEGA'):
            return None
        return json.loads(data[4:].decode('utf-8'))
    except:
        return None

def get_folder_links(url):
    """Extract all file links from a MEGA folder URL."""
    # Match new and old MEGA folder link formats
    m = re.search(r"mega.[^/]+/(?:folder/|#F!)([0-z-_]+)[#!]([0-z-_]+)", url)
    if not m:
        return "Error: Invalid MEGA folder URL"
    
    folder_id, folder_key_str = m.group(1), m.group(2)
    folder_key = base64_to_a32(folder_key_str)
    
    # Request folder contents from MEGA API
    try:
        res = requests.post('https://g.api.mega.co.nz/cs', 
                            params={'id': 0, 'n': folder_id},
                            data=json.dumps([{'a': 'f', 'c': 1, 'ca': 1, 'r': 1}]))
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        return f"Error connecting to MEGA API: {e}"
    
    if not data or 'f' not in data[0]:
        return "Error: No files found or access denied"
        
    nodes = data[0]['f']
    results = []
    for node in nodes:
        if 'k' not in node:
            continue
            
        # Node keys can be multiple, separated by '/'
        keys = node['k'].split('/')
        for k_part in keys:
            if ':' in k_part:
                _, k_str = k_part.split(':')
                try:
                    enc_key = base64_to_a32(k_str)
                    dec_key = decrypt_key(enc_key, folder_key)
                    
                    # File attribute decryption key
                    if node['t'] == 0: # File
                        attr_key = (dec_key[0] ^ dec_key[4], dec_key[1] ^ dec_key[5], 
                                    dec_key[2] ^ dec_key[6], dec_key[3] ^ dec_key[7])
                    else: # Folder
                        attr_key = dec_key
                        
                    attrs = decrypt_attr(base64_url_decode(node['a']), attr_key)
                    if attrs:
                        if node['t'] == 0: # Only add files to results
                            file_key = base64.urlsafe_b64encode(a32_to_str(dec_key)).decode('utf-8').replace('=', '')
                            results.append({
                                "name": attrs['n'],
                                "link": f"https://mega.nz/file/{node['h']}#{file_key}",
                                "size": node.get('s', 0)
                            })
                        break # Successfully decrypted this node
                except:
                    continue
                    
    return results

def format_size(size):
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <MEGA_FOLDER_URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    links = get_folder_links(url)
    
    if isinstance(links, str):
        print(links)
    else:
        print(f"{'Filename':<50} | {'Size':<10} | {'Direct Link'}")
        print("-" * 120)
        for item in links:
            print(f"{item['name']:<50} | {format_size(item['size']):<10} | {item['link']}")
