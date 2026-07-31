SDCC ?= sdcc
MAKEBIN ?= makebin
PYTHON ?= python3
BUILD := build
TARGET := $(BUILD)/amt630a-openpocket-er-tft050a3-2
SOURCES := src/main.c src/registers.c src/status_i2c.c
OBJECTS := $(patsubst src/%.c,$(BUILD)/%.rel,$(SOURCES))

.PHONY: all clean test manifest

all: $(TARGET).bin $(TARGET).bin.sha256 build-manifest.json

$(BUILD):
	mkdir -p $@

$(BUILD)/%.rel: src/%.c include/amt630a.h | $(BUILD)
	$(SDCC) -mmcs51 --model-small --iram-size 256 --xram-size 2048 \
		--code-size 65536 -Iinclude -c $< -o $@

$(TARGET).ihx: $(OBJECTS)
	$(SDCC) -mmcs51 --model-small --iram-size 256 --xram-size 2048 \
		--code-size 65536 --out-fmt-ihx $(OBJECTS) -o $@

$(TARGET).bin: $(TARGET).ihx
	$(MAKEBIN) -s 65536 $< $@

$(TARGET).bin.sha256: $(TARGET).bin
	sha256sum $< | awk '{print $$1}' > $@

build-manifest.json: $(TARGET).bin $(TARGET).bin.sha256 tools/manifest.py panel-timing.json
	$(PYTHON) tools/manifest.py

test: all
	$(PYTHON) -m unittest discover -s tests -v

clean:
	find $(BUILD) -type f -delete 2>/dev/null || true
	rmdir $(BUILD) 2>/dev/null || true
