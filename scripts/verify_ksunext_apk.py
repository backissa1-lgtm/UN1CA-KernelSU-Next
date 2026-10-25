#!/usr/bin/env python3
"""Verify exact, trusted upstream UAPI6 manager and bundled ARM64 ksud."""
from pathlib import Path
import hashlib, struct, sys, zipfile
APK="43acb0587741b845712a12c1ea08cacb8aede72118f4895312745a6769a45fda"
KSUD="cf2005f7eb9320cee100b8c3245c09b2ac4bd4080b0bd4872d65eb2e98811aa8"
SIGNER="79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7"
def lp(b,p=0):
    n=struct.unpack_from("<I",b,p)[0]
    assert p+4+n<=len(b)
    return b[p+4:p+4+n],p+4+n
def cert(b):
    e=b.rfind(bytes.fromhex("504b0506"))
    assert e>=0
    cd=struct.unpack_from("<I",b,e+16)[0]
    assert b[cd-16:cd]==b"APK Sig Block 42"
    n=struct.unpack_from("<Q",b,cd-24)[0]
    start=cd-8-n
    assert start>=0 and struct.unpack_from("<Q",b,start)[0]==n
    pairs=b[start+8:cd-24]
    p=0
    while p<len(pairs):
        length=struct.unpack_from("<Q",pairs,p)[0]
        ident=struct.unpack_from("<I",pairs,p+8)[0]
        if ident==0x7109871A:
            signers,_=lp(pairs[p+12:p+8+length])
            signer,_=lp(signers)
            signed,_=lp(signer)
            _,at=lp(signed)
            certs,_=lp(signed,at)
            der,_=lp(certs)
            return der
        p+=8+length
    raise AssertionError("No APK v2 signature")
def main():
    b=Path(sys.argv[1]).read_bytes()
    assert hashlib.sha256(b).hexdigest()==APK,"Unexpected APK bytes"
    der=cert(b)
    assert len(der)==998 and hashlib.sha256(der).hexdigest()==SIGNER,"Wrong signing identity"
    with zipfile.ZipFile(sys.argv[1]) as z:
        ksud=z.read("lib/arm64-v8a/libksud.so")
    assert hashlib.sha256(ksud).hexdigest()==KSUD,"UAPI6 daemon mismatch"
    print("Verified signed upstream UAPI6 APK and exact working ARM64 ksud")
if __name__=="__main__":
    main()
