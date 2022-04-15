CC = gcc
LIBS = -lrt
LINK_TARGET = shmlog
DEPS = \
	log_shm.c \
	cpulog.c \
	cpulog.h \
	memlog.h \
	apache_agent.h

REBUILDABLES = $(LINK_TARGET)

all : $(LINK_TARGET)

clean :
	rm -f $(REBUILDABLES)

$(LINK_TARGET) : $(DEPS)
	$(CC) -g -o $@ $^ $(LIBS)