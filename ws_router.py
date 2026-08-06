"""Импорт/экспорт списка IP через CSV-файл."""

from fastapi import APIRouter, File, Response, UploadFile

from services.csv_service import export_ips_to_csv, import_ips_from_csv

router = APIRouter(tags=["csv"])


@router.get("/export-csv/")
async def export_csv():
    csv_data = await export_ips_to_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ip_addresses.csv"},
    )


@router.post("/import-csv/")
async def import_csv(file: UploadFile = File(...)):
    added = await import_ips_from_csv(file)
    return {"message": "CSV imported successfully", "added": added}
