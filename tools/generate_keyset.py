#!/usr/bin/env python3
import tink
from tink import aead
from tink import cleartext_keyset_handle
import io


def generate_master_keyset():
    aead.register()
    keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    out = io.StringIO()
    writer = tink.JsonKeysetWriter(out)
    cleartext_keyset_handle.write(writer, keyset_handle)
    return out.getvalue()


if __name__ == "__main__":
    print(generate_master_keyset())
