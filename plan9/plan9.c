#include <u.h>
#include <libc.h>
//#include <tos.h>
#include <thread.h>
#include <draw.h>
#include <memdraw.h>
#include <mouse.h>
#include <cursor.h>

void
WindowTitle(const char *title)
{
	int f;

	f = open("/dev/label", OWRITE|OTRUNC|OCEXEC);
	if (f < 0)
		f = open("/mnt/term/dev/label", OWRITE|OTRUNC|OCEXEC);
	if (f < 0)
		return;
	write(f, title, strlen(title));
	close(f);
}

static Mousectl *mctl;
static Mouse mouse;

struct key_info {
	Rune	rune;
	int	type;
};

static struct key_info key_event;

enum {
	Ckey,
	Ckeytype,
	Cmouse,
	Cresize,
	Numchan,
};

static Alt salt[Numchan+1] = {
	[Ckey] = { nil, &key_event, CHANRCV },
	[Cmouse] = { nil, &mouse, CHANRCV },
	[Cresize] = { nil, nil, CHANRCV },
	[Numchan] = { nil, nil, CHANNOBLK }
};

static void
kbdproc(void *)
{
	int kfd;
	char buf[128];
	char *ptr;
	int size = 0;
	struct key_info key;

	threadsetname("kbdproc");
	if ((kfd = open("/dev/kbd", OREAD|OCEXEC)) < 0)
		sysfatal("/dev/kbd: %r");

	while (1) {
		if (size == 0) {
			size = read(kfd, buf, sizeof(buf));
			if (size <= 0)
				break;
		}
		ptr = buf;
		while (size > 0) {
			size -= strlen(ptr);
			key.type = (ptr[0] != 'k');
			ptr ++;
			while (*ptr) {
				ptr += chartorune(&key.rune, ptr);
				send(salt[Ckey].c, &key);
			}
		}
	}
	threadexits(nil);
}

int
PlatformInit(void)
{
	mctl = initmouse(nil, screen);
	if (mctl == nil)
		return -1;
	if(memimageinit() < 0)
		return -1;
	if(initdraw(nil, nil, "core") < 0)
		return -1;
	salt[Ckey].c = chancreate(sizeof(struct key_info), 20);
	salt[Cmouse].c = mctl->c;
	salt[Cresize].c = mctl->resizec;

	if (salt[Ckey].c == nil ||
		salt[Ckeytype].c == nil ||
		proccreate(kbdproc, nil, 4096) < 0)
		return -1;
	return 0;
}

void
PlatformDone(void)
{

}

void Delay(float n)
{
}
int WaitEvent(float n)
{
	return 0;
}

int WindowCreate(void)
{
	return 0;
}

void WindowResize(int w, int h)
{
}

void WindowUpdate(int x, int y, int w, int h)
{
}

unsigned char *WindowPixels(int *w, int *h)
{
	return nil;
}

void WindowMode(int n)
{
}

unsigned long Ticks(void)
{
	return 0;
}

double Time(void)
{
	return 0;
}

float GetScale(void)
{
	return 1.0f;
}

const char *GetPlatform(void)
{
	return "Plan9";
}

const char *GetExePath(const char *progname)
{
	return nil;
}

void Icon(unsigned char *ptr, int w, int h)
{
	return;
}

extern int sys_poll(void)
{
	switch (alt(salt)) {
	case Ckey:
		break;
	case Cmouse:
		break;
	case Cresize:
		break;
	}
	return 0;
}
