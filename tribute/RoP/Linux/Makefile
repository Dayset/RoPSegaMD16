# RoP Tribute — classic isometric app (M7, 2D), Linux build.
#
# Hand-written (not NetBeans-generated). Flags and link line mirror the
# Esenthel sample Project's Release makefile (Project/Linux/nbproject/
# Makefile-Release.mk), with paths adjusted: from RoP/Linux/, the engine
# root is ../../EsenthelEngine/ (the engine source lives in
# tribute/EsenthelEngine/, pinned in ../ENGINE_VERSION.txt).
#
# Build:  make -C tribute/RoP/Linux CONF=Release
#   (builds ../stdafx.h.pch, then ../RoP)
# Requires: Engine.a + ThirdPartyLibs built first (see ../../build.sh).
#   Engine:  make -C ../EsenthelEngine/Engine/Linux CONF=Release
#   ThirdPartyLibs: see ../../build.sh
#
# Compiler: clang++ (the engine's makefiles use clang, not g++).

CC  = clang
CXX = clang++

# App root (tribute/RoP) and engine root, relative to this dir (RoP/Linux).
APP_DIR    = ..
ENGINE_DIR = ../../EsenthelEngine
TPL_DIR    = $(ENGINE_DIR)/ThirdPartyLibs

CONF       = Release
OBJECTDIR  = build/$(CONF)/GNU-Linux
TARGET     = ../RoP

# --- Compiler flags (mirror the Esenthel sample Project, Release) ---
CXXFLAGS = -m64 -fshort-wchar -fpermissive -ffast-math -ffriend-injection \
	-Wno-int-to-pointer-cast -Wno-invalid-offsetof -Wno-comment \
	-Wno-parentheses -Wno-switch -Wno-null-dereference -Wno-empty-body \
	-Wno-address-of-temporary -Wno-return-type-c-linkage \
	-include ../stdafx.h -O3 -DDEBUG=0 -std=c++14

# --- Include paths (mirror the engine/sample compile) ---
INCLUDES = -I.. \
	-I$(ENGINE_DIR)/Engine/H/_ \
	-I$(TPL_DIR)/PhysX/PhysX/Include \
	-I$(TPL_DIR)/PhysX/PhysX/Include/cloth \
	-I$(TPL_DIR)/PhysX/PhysX/Include/common \
	-I$(TPL_DIR)/PhysX/PhysX/Include/extensions \
	-I$(TPL_DIR)/PhysX/PhysX/Include/geometry \
	-I$(TPL_DIR)/PhysX/PhysX/Include/vehicle \
	-I$(TPL_DIR)/PhysX/PhysX/Source/Common/src \
	-I$(TPL_DIR)/PhysX/PhysX/Source/GeomUtils/src \
	-I$(TPL_DIR)/PhysX/PhysX/Source/PhysXExtensions/src/serialization/Xml \
	-I$(TPL_DIR)/PhysX/PhysX/Source/PhysXMetaData/core/include \
	-I$(TPL_DIR)/PhysX/PhysX/Source/PhysXMetaData/extensions/include \
	-I$(TPL_DIR)/PhysX/PhysX/Source/PhysXVehicle/src \
	-I$(TPL_DIR)/PhysX/PhysX/Source/PhysXVehicle/src/PhysXMetaData/include \
	-I$(TPL_DIR)/PxShared/include \
	-I$(TPL_DIR)/PxShared/src/foundation/include \
	-I$(TPL_DIR)/PxShared/src/pvd/include \
	-I$(TPL_DIR)/Theora/include \
	-I$(TPL_DIR)/FreeType/lib/include \
	-I$(TPL_DIR)/Opus/lib/include \
	-I$(TPL_DIR)/Opus/file/include \
	-I$(TPL_DIR)/Vorbis/include \
	-I$(TPL_DIR)/Ogg/include \
	-I$(TPL_DIR)/FBX \
	-I$(TPL_DIR)/Bullet/lib/src \
	-I$(TPL_DIR)/VP/libvpx/third_party/libwebm \
	-I$(TPL_DIR)/FDK-AAC/lib/libAACdec/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libAACenc/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libFDK/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libMpegTPDec/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libMpegTPEnc/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libPCMutils/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libSBRdec/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libSBRenc/include \
	-I$(TPL_DIR)/FDK-AAC/lib/libSYS/include \
	-I$(TPL_DIR)

# --- Link: engine + third-party libs + system libs (mirror the sample) ---
# PhysX on Linux links the Dummy libs (ThirdPartyLibs/PhysX/Dummy/Linux);
# the real PhysX SDK is not in the engine repo. The engine .a references
# no real PhysX SDK symbols (verified: 0 undefined Px/physx:: symbols).
ENGINE_A = $(ENGINE_DIR)/Engine/Linux/dist/Release/GNU-Linux/EsenthelEngine.a
TPL_A = \
	$(TPL_DIR)/Recast/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Png/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Vorbis/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Theora/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/SQLite/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Webp/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/LZ4/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Ogg/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Tiff/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/FreeType/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Bullet/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Snappy/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/LZMA/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/FBX/Linux/libfbxsdk.a \
	$(TPL_DIR)/JpegTurbo/Linux/libturbojpeg.a \
	$(TPL_DIR)/Flac/Linux/libFLAC-static.a \
	$(TPL_DIR)/Opus/Linux/libopusfile.a \
	$(TPL_DIR)/Opus/Linux/libopus.a \
	$(TPL_DIR)/VP/Linux/libvpx.a \
	$(TPL_DIR)/LZHAM/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/Zstd/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/FDK-AAC/Linux/dist/Release/GNU-Linux/liblinux.a \
	$(TPL_DIR)/mbedTLS/Linux/dist/Release/GNU-Linux/liblinux.a

LDLIBSOPTIONS = \
	-L$(TPL_DIR)/PhysX/PhysX/Bin/linux64 \
	-L$(TPL_DIR)/PhysX/PhysX/Lib/linux64 \
	-L$(TPL_DIR)/PhysX/PxShared/bin/linux64 \
	-L$(TPL_DIR)/PhysX/PxShared/lib/linux64 \
	-L$(TPL_DIR)/PhysX/Dummy/Linux \
	$(ENGINE_A) $(TPL_A) \
	-lX11 -lXmu -lXxf86vm -lXinerama -lXrandr -lrt -lXi -lXcursor \
	-lGL -lopenal -lz -lodbc -ludev -lpthread -ldl

PHYSX_LIBS = -Wl,--start-group \
	-lPhysX3_x64 -lPhysX3Cooking_x64 -lPhysX3Extensions \
	-lPhysX3CharacterKinematic_x64 -lPhysX3Vehicle -lPhysX3Common_x64 \
	-lSimulationController -lSceneQuery -lLowLevelParticles \
	-lLowLevelCloth -lLowLevelDynamics -lLowLevelAABB -lLowLevel \
	-lPxTask -lPxFoundation_x64 -Wl,--end-group

# --- Sources ---
SOURCES = ../Source/RoP.cpp ../stdafx.cpp
OBJECTS = $(OBJECTDIR)/RoP.o $(OBJECTDIR)/stdafx.o
PCH     = ../stdafx.h.pch

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJECTS) $(ENGINE_A) $(TPL_A)
	@mkdir -p ..
	$(CXX) -no-pie -o $(TARGET) $(OBJECTS) $(LDLIBSOPTIONS) \
		-static-libstdc++ $(PHYSX_LIBS) -s

$(OBJECTDIR)/RoP.o: ../Source/RoP.cpp $(PCH)
	@mkdir -p $(OBJECTDIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -MMD -MP -MF "$(OBJECTDIR)/RoP.o.d" \
		-c -o $@ ../Source/RoP.cpp

$(OBJECTDIR)/stdafx.o: ../stdafx.cpp $(PCH)
	@mkdir -p $(OBJECTDIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -MMD -MP -MF "$(OBJECTDIR)/stdafx.o.d" \
		-c -o $@ ../stdafx.cpp

$(PCH): ../stdafx.h
	@mkdir -p ..
	@echo "Precompiling headers.."
	$(CXX) -x c++-header ../stdafx.h -o $(PCH) $(CXXFLAGS) $(INCLUDES)

clean:
	@rm -rf build $(PCH) $(TARGET)
