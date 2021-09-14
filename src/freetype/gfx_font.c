#include "../external.h"
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H
#include "../gfx.h"

static int initialized = 0;
FT_Library  library;

typedef struct {
	short int advance;
	short int width;
} glyph_t;

struct _font_t {
	FT_Face	face;
	img_t **cache;
	glyph_t *glyphs;
	float size;
	int height;
};

int
font_height(font_t *font)
{
	return font->height;
}

static glyph_t *
get_glyph(font_t *font, int idx)
{
	FT_GlyphSlot glyph;
	glyph_t *g;
	g = &font->glyphs[idx];
	if (g->advance > 0)
		return g;

	FT_Load_Glyph(font->face, idx, FT_LOAD_DEFAULT);
	glyph = font->face->glyph;
	g->advance = glyph->advance.x >> 6;
	g->width = glyph->metrics.width;
	return g;
}

int
font_width(font_t *font, const char *text)
{
	int x = 0;
	int idx;
	glyph_t *g;
	const char *p = text;
	unsigned codepoint;
	int xend = 0;
	while (*p) {
		p = utf8_to_codepoint(p, &codepoint);
		idx = FT_Get_Char_Index(font->face, codepoint);
		g = get_glyph(font, idx);
		x += g->advance;
		xend = g->width;
		if (xend > g->advance) {
			xend -= (xend - g->advance);
		} else
			xend = 0;
	}
	return x + xend;
}

font_t*
font_load(const char *filename, float size)
{
	int ok, sz;
	FT_Face face;
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
	sz = font->face->num_glyphs * sizeof(img_t *);
	font->cache = malloc(sz);
	if (!font->cache)
		goto err;
	memset(font->cache, 0, sz);

	sz = font->face->num_glyphs * sizeof(glyph_t);
	font->glyphs = malloc(sz);
	if (!font->glyphs)
		goto err;
	memset(font->glyphs, 0, sz);
	FT_Set_Char_Size(font->face, 0, size*64, 0, 72);
	face = font->face;
	font->height = round((face->bbox.yMax - face->bbox.yMin) * size / font->face->units_per_EM + 0.5);
	font->height = round((face->ascender - face->descender) * size / font->face->units_per_EM + 0.5);
	return font;
err:
	if (font->cache)
		free(font->cache);
	if (font->glyphs)
		free(font->glyphs);
	free(font);
	return NULL;
}

int
font_render(font_t *font, const char *text, img_t *img)
{
	int x = 0, y, xx, i, pos, idx, yoff;
	img_t *g;
	const char *p = text;
	unsigned codepoint;
	FT_Face face;
	FT_GlyphSlot glyph;
	glyph_t *gi;
	face = font->face;
	while (*p) {
		p = utf8_to_codepoint(p, &codepoint);
		idx = FT_Get_Char_Index(face, codepoint);
		FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT);
		g = font->cache[idx];
		if (!g) {
			glyph = face->glyph;
			FT_Render_Glyph(glyph, FT_RENDER_MODE_NORMAL);
			g = img_new(glyph->bitmap.width + glyph->bitmap_left, img->h);
			memset(g->ptr, 0, g->w * g->h * 4);
			i = 0;
			yoff = face->ascender * font->size / face->units_per_EM - glyph->bitmap_top;
			for (y=0; y < glyph->bitmap.rows; y++) {
				if (yoff + y >= g->h)
					break;
				pos = ((yoff + y) * g->w + glyph->bitmap_left) * 4;
				for (xx = 0; xx < glyph->bitmap.width; xx ++) {
					if (xx + glyph->bitmap_left >= g->w) {
						i += (glyph->bitmap.width - xx);
						break;
					}
					pos += 3;
					g->ptr[pos++] =  glyph->bitmap.buffer[i++];
				}
			}
			font->cache[idx] = g;
			gi = &font->glyphs[idx];
			gi->advance = glyph->advance.x >> 6;
			gi->width = glyph->metrics.width;
		} else
			gi = get_glyph(font, idx);
		img_pixels_blend(g, 0, 0, g->w, g->h,
			img, x, 0, PXL_BLEND_BLEND);
		x += gi->advance;
	}
	return 0;
}

void
font_free(font_t *font)
{
	int i;
	for (i = 0; i < font->face->num_glyphs; i++) {
		if (font->cache[i])
			free(font->cache[i]);
	}
	free(font->glyphs);
	free(font->cache);
	FT_Done_Face(font->face);
	free(font);
}
