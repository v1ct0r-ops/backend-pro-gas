def normalizar_validar_rut(rut: str) -> str:
    """Normaliza (uppercase, sin puntos, con guión) y valida el dígito verificador chileno.
    Devuelve el RUT en formato canónico: '12345678-9'.
    """
    rut = rut.strip().upper().replace(".", "")
    if "-" not in rut:
        raise ValueError("RUT debe incluir dígito verificador separado por '-' (ej: 12345678-9)")
    cuerpo, dv = rut.split("-", 1)
    if not cuerpo.isdigit() or len(cuerpo) < 7:
        raise ValueError("Cuerpo del RUT debe contener al menos 7 dígitos numéricos")

    digits = [int(d) for d in reversed(cuerpo)]
    factors = [2, 3, 4, 5, 6, 7]
    total = sum(d * factors[i % 6] for i, d in enumerate(digits))
    remainder = total % 11
    dv_calc_val = 11 - remainder
    if dv_calc_val == 11:
        dv_calculado = "0"
    elif dv_calc_val == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(dv_calc_val)

    if dv != dv_calculado:
        raise ValueError(f"Dígito verificador inválido para RUT '{rut}' (esperado: {dv_calculado})")
    return rut
