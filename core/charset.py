"""Character sets shared by visualizer modes."""

# Half-width Katakana (most authentic to the movie)
HALF_WIDTH_KATAKANA = "ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
# Full-width Katakana
FULL_WIDTH_KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
# Numbers and symbols
NUMBERS = "0123456789"
SYMBOLS = ":<>*+=-@#$%&"
# Latin (less common, for variety)
LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Combined character set (weighted towards Japanese for authenticity)
MATRIX_CHARS = HALF_WIDTH_KATAKANA * 3 + FULL_WIDTH_KATAKANA * 2 + NUMBERS + SYMBOLS
