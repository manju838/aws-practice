"""Generate a two-page product manual for a FICTIONAL kettle.

Every fact is invented, so if the assistant answers correctly it must have retrieved the
answer from the document (a model cannot know them). scripts/33-test-chat.sh asserts on these.
Usage: python tests/make_sample_pdf.py [output.pdf]
"""
import sys

import pymupdf

PAGE_1 = """NIMBUS NK-4471 PRESSURE KETTLE: OWNER'S MANUAL

About the company. Nimbus Appliances was founded in Lisbon in 1994 by two former marine engineers, Ines Carvalho and Tomas Rangel. The company builds small kitchen appliances and ships to 31 countries. The NK-4471 is its flagship model and was first released in March 2019.

Heating performance. The NK-4471 heats a full 1.2 litre load to 87.5 degrees Celsius in 42 seconds. This is possible because of the patented CoilSpiral element, which sits directly under the stainless steel base. The kettle never boils at full atmospheric pressure. Instead, the sealed lid raises the internal pressure slightly so that the water reaches the target temperature faster while using less energy.

Safety. A brass safety valve opens automatically at 1.8 bar. If the valve ever opens, unplug the kettle and wait ten minutes before touching the lid. The handle contains a thermal fuse that cuts power permanently if the base exceeds 140 degrees Celsius. Never fill the kettle above the MAX line, which is engraved at 1.2 litres."""

PAGE_2 = """Warranty and service. Every NK-4471 carries a warranty of 26 months from the date of purchase. The warranty covers the heating element, the safety valve and the thermal fuse. It does not cover limescale damage. The support desk answers on weekdays between 09:00 and 17:00 Lisbon time and can be reached with the serial number printed under the base.

Cleaning and descaling. Descale the kettle every 60 uses with a solution of citric acid. Fill to the MAX line, heat once, leave for thirty minutes, then rinse three times. Do not use vinegar, because it can attack the brass valve seat. The lid gasket should be replaced every 18 months; replacement gaskets are part number GK-207.

Colours and accessories. The NK-4471 is sold in Fjord Blue, Sand and Graphite. An optional travel case, part number TC-88, holds the kettle and cable. The cable is 1.1 metres long and the plug type is selected at checkout."""


def main(out="nimbus-kettle-manual.pdf"):
    doc = pymupdf.open()
    for text in (PAGE_1, PAGE_2):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 780), text, fontsize=11)
    doc.save(out)
    print(f"wrote {out} ({len(doc)} pages)")


if __name__ == "__main__":
    main(*sys.argv[1:2])
