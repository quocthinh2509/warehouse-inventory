from erp_the20.repositories import profile_repository as repo

_ALLOWED_FIELDS = {
    "full_name","cccd","date_of_birth","address","first_day_in_job","email",
    "doc_link","picture_link","offer_content","salary","degree","old_company",
    "tax_code","bhxh","car","temporary_address","phone","emergency_contact","emergency_phone","note"
}

def upsert(user_id: int, payload: dict):
    data = {k: v for k, v in payload.items() if k in _ALLOWED_FIELDS}
    return repo.save_profile(user_id, **data)
