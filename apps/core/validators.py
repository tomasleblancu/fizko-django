"""
Shared validators for Chilean business rules and data validation
"""
import re
from rest_framework import serializers


def validate_rut(rut_number, dv):
    """
    Validates Chilean RUT (Rol Único Tributario)
    
    Args:
        rut_number (str): RUT number without DV (7-8 digits)
        dv (str): Verification digit (0-9 or K)
    
    Returns:
        bool: True if RUT is valid
    """
    try:
        # Clean and validate format
        rut_clean = str(rut_number).strip().replace(".", "").replace("-", "")
        dv_clean = str(dv).strip().upper()
        
        # Validate format
        if not re.match(r'^\d{7,8}$', rut_clean):
            return False
        
        if not re.match(r'^[0-9K]$', dv_clean):
            return False
        
        # Calculate verification digit
        rut_int = int(rut_clean)
        multiplier = 2
        sum_total = 0
        
        while rut_int:
            sum_total += (rut_int % 10) * multiplier
            rut_int //= 10
            multiplier += 1
            if multiplier == 8:
                multiplier = 2
        
        remainder = 11 - (sum_total % 11)
        
        if remainder == 11:
            calculated_dv = '0'
        elif remainder == 10:
            calculated_dv = 'K'
        else:
            calculated_dv = str(remainder)
        
        return calculated_dv == dv_clean
        
    except (ValueError, TypeError):
        return False


def validate_chilean_rut(value):
    """
    DRF validator for full Chilean RUT format (XX.XXX.XXX-X or XXXXXXXX-X)
    """
    if not value:
        raise serializers.ValidationError("RUT es requerido")
    
    # Clean the RUT
    rut_clean = str(value).strip().replace(".", "").replace(" ", "")
    
    # Check format
    if not re.match(r'^\d{7,8}-[0-9K]$', rut_clean.upper()):
        raise serializers.ValidationError(
            "Formato de RUT inválido. Use formato XXXXXXXX-X"
        )
    
    # Split RUT and DV
    rut_number, dv = rut_clean.split('-')
    
    # Validate using the RUT algorithm
    if not validate_rut(rut_number, dv):
        raise serializers.ValidationError("RUT inválido")
    
    return value


def validate_rut_parts(rut_number, dv):
    """
    DRF validator for RUT in separate parts
    """
    if not validate_rut(rut_number, dv):
        raise serializers.ValidationError(
            "Combinación de RUT y DV inválida"
        )


def validate_positive_amount(value):
    """
    Validates that monetary amounts are positive
    """
    if value < 0:
        raise serializers.ValidationError("El monto debe ser positivo")
    return value


def validate_percentage(value):
    """
    Validates percentage values (0-100)
    """
    if not (0 <= value <= 100):
        raise serializers.ValidationError("El porcentaje debe estar entre 0 y 100")
    return value


def validate_tax_period(value):
    """
    Validates tax period format (YYYY-MM or YYYY)
    """
    if not re.match(r'^\d{4}(-\d{2})?$', str(value)):
        raise serializers.ValidationError(
            "Formato de período inválido. Use YYYY para anual o YYYY-MM para mensual"
        )
    return value


def validate_folio_number(value):
    """
    Validates document folio numbers (must be positive)
    """
    if value <= 0:
        raise serializers.ValidationError("El número de folio debe ser positivo")
    return value


def format_rut(rut_number, dv):
    """
    Formats RUT number with standard Chilean format
    
    Args:
        rut_number (str): RUT number
        dv (str): Verification digit
    
    Returns:
        str: Formatted RUT (XX.XXX.XXX-X)
    """
    rut_str = str(rut_number).zfill(8)  # Pad with zeros if needed
    
    if len(rut_str) == 7:
        return f"{rut_str[0]}.{rut_str[1:4]}.{rut_str[4:7]}-{dv}"
    elif len(rut_str) == 8:
        return f"{rut_str[0:2]}.{rut_str[2:5]}.{rut_str[5:8]}-{dv}"
    else:
        return f"{rut_str}-{dv}"


def validate_email_list(value):
    """
    Validates a list of email addresses
    """
    if not isinstance(value, list):
        raise serializers.ValidationError("Debe ser una lista de emails")
    
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for email in value:
        if not email_regex.match(str(email)):
            raise serializers.ValidationError(f"Email inválido: {email}")
    
    return value


def validate_phone_number(value):
    """
    Validates and normalizes Chilean phone number format.
    Returns normalized format without + prefix.
    """
    if not value:
        return value

    # Clean input
    phone_clean = str(value).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Remove + prefix if present
    if phone_clean.startswith('+'):
        phone_clean = phone_clean[1:]

    # Chilean phone patterns and their normalized forms
    phone_patterns = [
        (r'^56[0-9]{8,9}$', lambda x: x),  # Already correct format: 56XXXXXXXXX
        (r'^09[0-9]{8}$', lambda x: f"569{x[2:]}"),  # Mobile: 09XXXXXXXX -> 569XXXXXXXX
        (r'^2[0-9]{7,8}$', lambda x: f"562{x[1:]}"),  # Santiago landline: 2XXXXXXX -> 562XXXXXXX
        (r'^[3-7][0-9]{7}$', lambda x: f"56{x}"),  # Regional landlines: XXXXXXX -> 56XXXXXXX
        (r'^9[0-9]{8}$', lambda x: f"56{x}"),  # Mobile without 0: 9XXXXXXXX -> 569XXXXXXXX
    ]

    # Try to match and normalize
    for pattern, normalizer in phone_patterns:
        if re.match(pattern, phone_clean):
            normalized = normalizer(phone_clean)
            # Final validation: must be 56 + 8-9 digits
            if re.match(r'^56[0-9]{8,9}$', normalized):
                return normalized

    raise serializers.ValidationError(
        "Formato de teléfono inválido. Use formato chileno: +56 9 XXXX XXXX o equivalente"
    )

    return value


def validate_document_type_code(value):
    """
    Validates SII document type codes
    """
    valid_codes = [33, 34, 39, 41, 46, 52, 56, 61, 110, 111, 112]
    
    if value not in valid_codes:
        raise serializers.ValidationError(
            f"Tipo de documento inválido. Códigos válidos: {valid_codes}"
        )
    
    return value


def calculate_iva(net_amount, rate=19):
    """
    Calculates IVA (Chilean VAT) for a given net amount
    
    Args:
        net_amount (Decimal): Net amount
        rate (int): IVA rate percentage (default 19%)
    
    Returns:
        Decimal: IVA amount
    """
    from decimal import Decimal
    return net_amount * (Decimal(rate) / 100)


def calculate_total_with_iva(net_amount, rate=19):
    """
    Calculates total amount including IVA
    """
    return net_amount + calculate_iva(net_amount, rate)