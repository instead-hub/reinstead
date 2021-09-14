#include "../external.h"
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H
#include "../gfx.h"

static int initialized = 0;
FT_Library  library;

struct _font_t {
	FT_Face	face;
	float size;
	int height;
};

int
font_height(font_t *font)
{
	return font->height;
}

int
font_width(font_t *font, const char *text)
{
	int x = 0;
	int idx;
	const char *p = text;
	unsigned codepoint;
	int xend = 0;
	while (*p) {
		p = utf8_to_codepoint(p, &codepoint);
		idx = FT_Get_Char_Index(font->face, codepoint);
		FT_Load_Glyph(font->face, idx, FT_LOAD_DEFAULT);
		x += font->face->glyph->advance.x >> 6;
		xend = font->face->glyph->metrics.width >> 6;
		if (font->face->glyph->metrics.width > font->face->glyph->advance.x) {
			xend -= (font->face->glyph->metrics.width - font->face->glyph->advance.x) >> 6;
		} else
			xend = 0;
	}
	return x + xend;
}

font_t*
font_load(const char *filename, float size)
{
	int ok;
	font_t *font = NULL;
	if (!initialized) {
		FT_Init_FreeType(&library);
		initialized = 1;
	}
	font = malloc(sizeof(font_t));
	if (!font)
		goto err;
	memset(font, 0, sizeof(font_t));
	font->size = size;
	ok = !FT_New_Face(library, filename, 0, &font->face);
	if (!ok)
		goto err;
	FT_Set_Char_Size(font->face, 0, size*64, 0, 72);
	font->height = round((font->face->bbox.yMax - font->face->bbox.yMin) * size / font->face->units_per_EM + 0.5);
	return font;
err:
	free(font);
	return NULL;
}

int
font_render(font_t *font, const char *text, img_t *img)
{
	int x = 0, y, xx, i, pos, idx, yoff;
	const char *p = text;
	unsigned codepoint;
	FT_Face face;
	FT_GlyphSlot glyph;
	face = font->face;
	glyph = face->glyph;
	while (*p) {
		p = utf8_to_codepoint(p, &codepoint);
		idx = FT_Get_Char_Index(face, codepoint);
		FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT);
		FT_Render_Glyph(glyph, FT_RENDER_MODE_NORMAL);
		i = 0;
		yoff = face->bbox.yMax * font->size / face->units_per_EM - glyph->bitmap_top;
		for (y=0; y < glyph->bitmap.rows; y++) {
			if (yoff + y >= img->h)
				break;
			pos = (yoff + y) * img->w * 4 + (x + glyph->bitmap_left) * 4;
			for (xx = 0; xx < glyph->bitmap.width; xx++) {
				if (x + xx + glyph->bitmap_left >= img->w) {
					i += (glyph->bitmap.width - xx);
					break;
				}
				if (glyph->bitmap.buffer[i]) {
					img->ptr[pos ++] = glyph->bitmap.buffer[i];
					img->ptr[pos ++] = glyph->bitmap.buffer[i];
					img->ptr[pos ++] = glyph->bitmap.buffer[i];
					img->ptr[pos ++] = glyph->bitmap.buffer[i];
				} else
					pos += 4;
				i++;
			}
		}
		x += glyph->advance.x >> 6;
	}
	return 0;
}

void
font_free(font_t *font)
{
	FT_Done_Face(font->face);
	free(font);
}
