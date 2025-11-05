from dronecan.dsdl import signature

# Your message definition
dsdl_text = """# uavcan.mpu.Vibration
uint8 id
float16 vibration_metrics
float16 dominant_frequency
float16 dominant_snr
"""

# Calculate signature
sig = signature.compute_signature(dsdl_text)
print(f"Signature: 0x{sig:016x}")