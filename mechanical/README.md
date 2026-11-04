# Mechanical design R0.1

Start with [the original design notes](README_原模型说明.md) and [illustrated model report](docs/BottleSorter_R01_Model_Report.pdf).

- `source/BottleSorter_R01_PARAMETRIC.f3d`: editable Fusion source with parameters/history.
- `exports/BottleSorter_R01_ASSEMBLY.step`: exchange assembly; does not retain the Fusion timeline.
- `exports/STL_PROVISIONAL.zip`: provisional printable meshes, millimetres.
- `exports/FIRST_TEST_PRINT`: selected local fit-test candidates, not records of completed printing.
- `exports/parameters.csv` and `parts_list.csv`: design parameters and CAD parts inventory.
- `images`: assembly, top, section and detail previews.

Current concept uses a common tray carrying three bins. It is mechanically different from the earlier -30/0/+30 sorting chute. Refer to ../docs/three-bin-migration.md before adapting firmware. Dimensions, interfaces and load capacity require physical confirmation; file existence is not validation.
