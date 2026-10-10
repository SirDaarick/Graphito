"""CharCNN v2: symmetric preprocessing, padding-invariant model and windowed scoring.

The legacy modules in `models.char_cnn` stay frozen and keep serving v1 checkpoints; everything
new lives in this subpackage. Submodules are imported explicitly (no re-exports) so importing
the package stays cheap and side-effect free.
"""
