"""Generate a synthetic packing-list PDF for end-to-end smoke testing."""
from pathlib import Path

import fitz

Path("uploads").mkdir(exist_ok=True)

doc = fitz.open()
page = doc.new_page(width=842, height=595)  # A4 landscape

y = 50
page.insert_text((60, y), "COMMERCIAL INVOICE / PACKING LIST", fontsize=14)
y += 20
page.insert_text((60, y), "CNF SHANGHAI PORT", fontsize=10)
y += 30

rows = [
    ["No", "Description of Goods", "Qnty (CBM)", "Unit Price CNF $/m3", "Amount CNF $"],
    ["1", "COMMERCIAL PLYWOOD 1220X2440X5MM MR E1 POPLEAR ARSER-PLY", "12.36", "285.00", "3,522.60"],
    ["2", "COMMERCIAL PLYWOOD 1220X2440X5MM MR E1 POPLEAR ARSER-PLY", "8.40", "285.00", "2,394.00"],
    ["3", "COMMERCIAL PLYWOOD 1220X2440X12MM E2 COMBI ARSER-PLY", "25.60", "352.00", "9,011.20"],
    ["4", "FILM FACED PLYWOOD 1220X2440X18MM BLACK FILM BROWN FILM ECOPLY EUCA QUALITY", "30.00", "465.00", "13,950.00"],
    ["5", "MELAMINE MDF 1220X2440X15MM Warm white YS003 MR POPLAR " "SUNWELL", "18.50", "318.00", "5,883.00"],
    ["6", "MELAMINE MDF 1220X2440X15MM Walnut 790-3 E1 POPLAR SUNWELL", "6.25", "318.00", "1,987.50"],
    ["7", "PAPER OVERLAY MDF 1220X2440X17MM SATIN E2 COMBI HANTEX", "9.80", "296.00", "2,900.80"],
    ["8", "COMMERCIAL PLYWOOD 2135X915X5MM MR E1 POPLAR ARSER-PLY", "4.32", "302.00", "1,304.64"],
    ["", "TOTAL CNF SHANGHAI", "", "", "40,953.74"],
]
x_cols = [60, 100, 560, 660, 750]
for i, row in enumerate(rows):
    bold = i == 0 or row[1].startswith("TOTAL")
    if bold:
        page.draw_line(fitz.Point(x_cols[0], y - 10), fitz.Point(x_cols[-1] + 60, y + 2), color=(0, 0, 0))
    for j, cell in enumerate(row):
        page.insert_text((x_cols[j], y), cell, fontsize=9)
    y += 20

y += 20
page.insert_text((60, y), "Break Bulk Shipment. Payment by T/T within 15 days after B/L date.", fontsize=9)
page.insert_text((60, y + 15), "Origin: China. Packing: standard export pallets, pcs/crts as per packing detail.", fontsize=9)

doc.save("uploads/test_packing_list.pdf")
print("saved uploads/test_packing_list.pdf")
