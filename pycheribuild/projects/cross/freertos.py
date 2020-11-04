#
# SPDX-License-Identifier: BSD-2-Clause
#
# Author: Hesham Almatary <Hesham.Almatary@cl.cam.ac.uk>
#
# This software was developed by SRI International and the University of
# Cambridge Computer Laboratory (Department of Computer Science and
# Technology) under DARPA contract HR0011-18-C-0016 ("ECATS"), as part of the
# DARPA SSITH research programme.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
import os

from .crosscompileproject import (CheriConfig, CompilationTargets, CrossCompileAutotoolsProject, DefaultInstallDir,
                                  GitRepository)
from ...config.loader import ComputedDefaultValue


class BuildFreeRTOS(CrossCompileAutotoolsProject):
    repository = GitRepository("https://github.com/CTSRD-CHERI/FreeRTOS-mirror",
                               force_branch=True, default_branch="hmka2-compartments-wip")
    target = "freertos"
    project_name = "freertos"
    dependencies = ["newlib", "compiler-rt-builtins"]
    is_sdk_target = True
    needs_sysroot = False  # We don't need a complete sysroot
    supported_architectures = [
        CompilationTargets.BAREMETAL_NEWLIB_RISCV64_PURECAP,
        CompilationTargets.BAREMETAL_NEWLIB_RISCV64]
    default_install_dir = DefaultInstallDir.SYSROOT

    # FreeRTOS Demos to build
    supported_freertos_demos = [
        # Generic/simple (CHERI-)RISC-V Demo that runs main_blinky on simulators
        # and simple SoCs
        "RISC-V-Generic"]

    # Map Demos and the FreeRTOS apps we support building/running for
    supported_demo_apps = {"RISC-V-Generic": ["main_blinky",
                                              "main_compartment_test",
                                              "main_peekpoke",
                                              "main_servers",
                                              "modbus_baseline",
                                              "modbus_baseline_microbenchmark",
                                              "modbus_cheri_layer",
                                              "modbus_cheri_layer_microbenchmark",
                                              "modbus_macaroons_layer",
                                              "modbus_macaroons_layer_microbenchmark",
                                              "modbus_cheri_macaroons_layers",
                                              "modbus_cheri_macaroons_layers_microbenchmark"
                                             ]}

    default_demo = "RISC-V-Generic"
    default_demo_app = "main_blinky"
    default_build_system = "waf"

    def _run_waf(self, *args, **kwargs):
        cmdline = ["./waf", "-t", self.source_dir / str("FreeRTOS/Demo/" + self.demo), "-o", self.build_dir] + list(args)
        if self.config.verbose:
            cmdline.append("-v")
        return self.run_cmd(cmdline, cwd=self.source_dir  / str("FreeRTOS/Demo/" + self.demo), **kwargs)

    def __init__(self, config: CheriConfig):
        super().__init__(config)
        self.compiler_resource = self.get_compiler_info(self.CC).get_resource_dir()

        self.default_demo_app = "qemu_virt-" + self.target_info.get_riscv_arch_string(self.crosscompile_target,
                                                                                      softfloat=True) + \
                                self.target_info.get_riscv_abi(self.crosscompile_target, softfloat=True)

        # We only support building FreeRTOS with llvm from cheribuild
        self.make_args.set(TOOLCHAIN="llvm")

        # For backward compatibility. CheriFreeRTOS used to be built within a NIX env.
        # Override that with no and set the appopriate flags here.
        self.make_args.set(NIX_ENV="no")

        # Only build 64-bit FreeRTOS as cheribuild currently only supports building
        # for RV64
        self.make_args.set(RISCV_XLEN="64")

        # Set sysroot Makefile arg to pick up libc
        self.make_args.set(SYSROOT=str(self.sdk_sysroot))

        # Add compiler-rt location to the search path
        # self.make_args.set(LDFLAGS="-L"+str(self.compiler_resource / "lib"))

        if self.target_info.target.is_cheri_purecap():
            # CHERI-RISC-V sophisticated Demo with more advanced device drivers
            # and currently only runs on FPGA-GFE, purecap
            self.supported_freertos_demos.append("RISC-V_Galois_P1")
            self.supported_demo_apps["RISC-V_Galois_P1"] = ["main_blinky", "main_netboot"]
            self.supported_demo_apps["RISC-V-Generic"].append("main_compartment_test")

            self.make_args.set(EXTENSION="cheri")

    @classmethod
    def setup_config_options(cls, **kwargs):
        super().setup_config_options(add_common_cross_options=False, **kwargs)

        cls.build_system = cls.add_config_option(
            "build_system", metavar="BUILD", show_help=True,
            default=cls.default_build_system,
            help="The FreeRTOS Demo Build System.")  # type: str

        cls.demo = cls.add_config_option(
            "demo", metavar="DEMO", show_help=True,
            default=cls.default_demo,
            help="The FreeRTOS Demo build.")  # type: str

        cls.demo_app = cls.add_config_option(
            "prog", metavar="PROG", show_help=True,
            default=cls.default_demo_app,
            help="The FreeRTOS program to build.")  # type: str

        cls.platform = cls.add_config_option(
            "platform", metavar="PLATFORM", show_help=True,
            default="qemu_virt",
            help="The FreeRTOS platform to build for.")  # type: str

        cls.demo_bsp = cls.add_config_option(
            "bsp", metavar="BSP", show_help=True,
            default=ComputedDefaultValue(function=lambda _, p: p.default_demo_bsp(),
                                         as_string="target-dependent default"),
            help="The FreeRTOS BSP to build. This is only valid for the "
                 "paramterized RISC-V-Generic. The BSP option chooses "
                 "platform, RISC-V arch and RISC-V abi in the "
                 "$platform-$arch-$abi format. See RISC-V-Generic/README for more details")

    def default_demo_bsp(self):
        return "qemu_virt-" + self.target_info.get_riscv_arch_string(self.crosscompile_target, softfloat=True) + "-" + \
               self.target_info.get_riscv_abi(self.crosscompile_target, softfloat=True)

    def run_compartmentalize(self, *args, **kwargs):
        cmdline = ["./compartmentalize.py"]
        return self.run_cmd(cmdline, cwd=self.source_dir / str("FreeRTOS/Demo/" + self.demo), **kwargs)

    def compile(self, **kwargs):

        if self.build_system == "waf":
            self._run_waf("build", self.config.make_j_flag)
            return

        self.make_args.set(BSP=self.demo_bsp)

        if self.demo_app == "main_compartment_test":
          self.run_compartmentalize()

        # Need to clean before/between building apps, otherwise
        # irrelevant objs will be picked up from incompatible apps/builds
        self.make_args.set(PROG=self.demo_app)
        self.run_make("clean", cwd=self.source_dir / str("FreeRTOS/Demo/" + self.demo))

        self.run_make(cwd=self.source_dir / str("FreeRTOS/Demo/" + self.demo))
        self.move_file(self.source_dir / str("FreeRTOS/Demo/" + self.demo + "/" + self.demo_app + ".elf"),
                       self.source_dir / str("FreeRTOS/Demo/" + self.demo + "/" + self.demo + self.demo_app + ".elf"))

    def configure(self):
        if self.build_system == "waf":

            if "modbus" in self.demo_app:
                program_root = "./modbus_demo"
            elif "servers" in self.demo_app:
                program_root = "./demo/servers"
            else:
                program_root = "/no/path"

            config_options = [
                          "--prefix", str(self.real_install_root_dir) + '/FreeRTOS/Demo/',
                          "--program", self.demo_app,
                          "--toolchain", "llvm",
                          "--riscv-platform", self.platform,
                          "--program-path", program_root,
                          "--sysroot",  str(self.sdk_sysroot)
                          ]

            config_options += ["--purecap"] if self.target_info.target.is_cheri_purecap() else []

            self._run_waf("distclean", "configure", *config_options)

    def install(self, **kwargs):
        if self.build_system == "waf":
            self._run_waf("install")
            return

        self.install_file(
            self.source_dir / str("FreeRTOS/Demo/" + self.demo + "/" + self.demo + self.demo_app + ".elf"),
            self.real_install_root_dir / str("FreeRTOS/Demo/bin/" + self.demo + "_" + self.demo_app + ".elf"))

    def process(self):

        if self.demo not in self.supported_freertos_demos:
            self.fatal("Demo " + self.demo + "is not supported")

        if self.demo_app not in self.supported_demo_apps[self.demo]:
            self.fatal(self.demo + " Demo doesn't support/have " + self.demo_app)

        with self.set_env(PATH=str(self.sdk_bindir) + ":" + os.getenv("PATH", ""),
                          # Add compiler-rt location to the search path
                          LDFLAGS="-L" + str(self.compiler_resource / "lib")):
            super().process()
