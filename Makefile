# Makefile for BOS-Radio-Bridge (Analog_Bridge for Raspberry Pi ARM64)
# Optimized for Raspberry Pi OS (ARM64) - Performance build

# Compiler settings
CXX = g++
CC = gcc

# Target architecture: ARM64 (aarch64)
ARCH = aarch64
CPU_FLAGS = -march=armv8-a+fp+simd -mtune=cortex-a72 -O3 -flto

# Compiler flags for performance optimization
CXXFLAGS = -std=c++17 -Wall -Wextra -Werror -pthread $(CPU_FLAGS) -fPIC -fstack-protector-strong
CFLAGS = -std=c11 -Wall -Wextra -Werror $(CPU_FLAGS) -fPIC -fstack-protector-strong

# Linker flags
LDFLAGS = -pthread -lrt -ldl $(CPU_FLAGS)

# Include directories (adjust paths as needed)
INCLUDES = -I./include -I/usr/local/include -I/usr/include

# Library directories
LIBDIRS = -L./lib -L/usr/local/lib -L/usr/lib/aarch64-linux-gnu

# Libraries (add softAMBE and other required libraries)
LIBS = -lpthread -lrt -ldl

# Source files (adjust based on actual source structure)
SOURCES = $(wildcard src/*.cpp)
OBJECTS = $(SOURCES:.cpp=.o)

# Target binary
TARGET = Analog_Bridge

# Installation paths for Raspberry Pi
PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
CONFDIR = /etc
SYSTEMDDIR = /etc/systemd/system

# Default target
all: $(TARGET)

# Build target
$(TARGET): $(OBJECTS)
	@echo "Linking $(TARGET)..."
	$(CXX) $(OBJECTS) $(LDFLAGS) $(LIBDIRS) $(LIBS) -o $(TARGET)
	@echo "Build complete: $(TARGET)"

# Compile source files
%.o: %.cpp
	@echo "Compiling $<..."
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -f $(OBJECTS) $(TARGET)
	rm -f *.o *~ core

# Install binary and configuration
install: $(TARGET)
	@echo "Installing $(TARGET)..."
	install -d $(BINDIR)
	install -m 755 $(TARGET) $(BINDIR)/
	install -d $(CONFDIR)
	install -m 644 Analog_Bridge/Analog_Bridge.ini $(CONFDIR)/Analog_Bridge.ini
	@echo "Installation complete"

# Uninstall
uninstall:
	@echo "Uninstalling $(TARGET)..."
	rm -f $(BINDIR)/$(TARGET)
	rm -f $(CONFDIR)/Analog_Bridge.ini
	@echo "Uninstallation complete"

# Debug build
debug: CXXFLAGS += -g -DDEBUG -O0
debug: CFLAGS += -g -DDEBUG -O0
debug: $(TARGET)

# Help target
help:
	@echo "BOS-Radio-Bridge Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all       - Build optimized binary (default)"
	@echo "  debug     - Build debug version"
	@echo "  clean     - Remove build artifacts"
	@echo "  install   - Install binary and configuration"
	@echo "  uninstall - Remove installed files"
	@echo "  help      - Show this help message"
	@echo ""
	@echo "Note: This Makefile assumes source code structure exists."
	@echo "Adjust SOURCES, INCLUDES, and LIBS based on actual project structure."

.PHONY: all clean install uninstall debug help

