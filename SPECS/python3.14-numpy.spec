%global python3_pkgversion 3.14
#uncomment next line for a release candidate or a beta
#%%global relc rc1

# Simple way to disable tests
# RHEL: Tests disabled due to missing dependencies
%if 0%{?flatpak} || 0%{?rhel} || 0%{?fedora}
%bcond_with tests
%else
%bcond_without tests
%endif

%if 0%{?fedora} >= 33 || 0%{?rhel} >= 9
%global blaslib flexiblas
%global blasvar %{nil}
%else
%global blaslib openblas
%global blasvar p
%endif

%global modname numpy

Name:           python%{python3_pkgversion}-numpy
Version:        2.3.4
Release:        2%{?dist}
Summary:        A fast multidimensional array facility for Python

# Everything is BSD-3-Clause except...
# numpy/core/include/numpy/libdivide: Zlib OR BSL-1.0
# numpy/core/src/multiarray/dragon4.*: MIT
# numpy/random/src/mt19937/randomkit.h: MIT
# numpy/random/src/pcg64: MIT AND Apache-2.0
# numpy/random/src/sfc64: MIT
License:        BSD-3-Clause AND MIT AND Apache-2.0 AND (Zlib OR BSL-1.0)
URL:            http://www.numpy.org/
Source0:        https://github.com/%{modname}/%{modname}/releases/download/v%{version}/%{modname}-%{version}.tar.gz

# Resolve issues identified by coverity static analysis
# Resolved upstream:
# https://github.com/numpy/numpy/pull/30877
# https://github.com/numpy/numpy/pull/30647
# https://github.com/numpy/numpy/pull/30475
# Sent upstream:
# https://github.com/numpy/numpy/pull/31819
Patch:          coverity-fixes.patch

# Fix test_validate_transcendentals skip to match SVML dispatch
# Sent upstream: https://github.com/numpy/numpy/pull/31333
Patch:          fix-test_validate_transcendentals-x86_64.patch

# Fix signed overflow issue in npy_gcd for INT_MIN on s390x
# Resolved upstream:
# https://github.com/numpy/numpy/pull/31360
Patch:          fix-signed-overflow-s390x.patch

# Enable CET hardware protections for the AVX-512 assembly
# Sent upstream: https://github.com/numpy/SVML/pull/8
Patch:          cet-protections.patch

BuildRequires:  python%{python3_pkgversion}-devel
BuildRequires:  gcc-gfortran gcc gcc-c++
BuildRequires:  lapack-devel
%if 0%{?fedora}
BuildRequires:  libdivide-devel
%endif
BuildRequires:  ninja-build
%if %{with tests}
BuildRequires:  python%{python3_pkversion}-hypothesis
BuildRequires:  python%{python3_pkversion}-pytest
BuildRequires:  python%{python3_pkversion}-test
BuildRequires:  python%{python3_pkgversion}-typing-extensions
%endif
BuildRequires: %{blaslib}-devel
BuildRequires: chrpath
# Upstream does not support splitting out f2py
#  https://github.com/numpy/numpy/issues/28016
#  https://bugzilla.redhat.com/show_bug.cgi?id=2332307
Requires:       python%{python3_pkgversion}-numpy-f2py%{?_isa} = %{version}-%{release}

%if !0%{?fedora}
Provides:       bundled(libdivide) = 3.0
%endif

%description
NumPy is a general-purpose array-processing package designed to
efficiently manipulate large multi-dimensional arrays of arbitrary
records without sacrificing too much speed for small multi-dimensional
arrays.  NumPy is built on the Numeric code base and adds features
introduced by numarray as well as an extended C-API and the ability to
create arrays of arbitrary type.

There are also basic facilities for discrete fourier transform,
basic linear algebra and random number generation. Also included in
this package is a version of f2py that works properly with NumPy.

%package -n python%{python3_pkgversion}-numpy-f2py
Summary:        f2py for numpy
Requires:       python%{python3_pkgversion}-numpy%{?_isa} = %{version}-%{release}
Requires:       python%{python3_pkgversion}-devel
Provides:       python%{python3_pkgversion}-f2py = %{version}-%{release}

%description -n python%{python3_pkgversion}-numpy-f2py
This package includes a version of f2py that works properly with NumPy.

%prep
%autosetup -n %{modname}-%{version} -p1

# The bundled meson searches for cython or cython3 command. We add cython-3.X:
sed -i "s/\['cython', 'cython3'\]/\['cython', 'cython3', 'cython-3.14'\]/" vendored-meson/meson/mesonbuild/compilers/detect.py

# openblas is provided by flexiblas by default; otherwise,
# Use openblas pthreads as recommended by upstream (see comment in site.cfg.example)
cat >> site.cfg <<EOF
[openblas]
libraries = %{blaslib}%{blasvar}
library_dirs = %{_libdir}
EOF

%if 0%{?fedora}
# Unbundle libdivide
sed -i 's,"numpy/libdivide/libdivide.h",<libdivide.h>,' \
    numpy/_core/src/umath/loops.c.src
%endif

%generate_buildrequires
%pyproject_buildrequires -R -Csetup-args=-Dblas=flexiblas -Csetup-args=-Dlapack=lapack

%build
%set_build_flags
# Allow libdivide to use vector instructions where possible
%ifarch x86_64
%if 0%{?rhel} > 9
# x86_64-v3
sed -i '/libdivide\.h/i#define LIBDIVIDE_AVX2' numpy/_core/src/umath/loops.c.src
%else
# x86_64-v1 or x86_64-v2
sed -i '/libdivide\.h/i#define LIBDIVIDE_SSE2' numpy/_core/src/umath/loops.c.src
%endif
%elifarch aarch64
sed -i '/libdivide\.h/i#define LIBDIVIDE_NEON' numpy/_core/src/umath/loops.c.src
%endif

#fix flags for ELN ppc64le
%if 0%{?rhel} >= 10
%ifarch ppc64le
find . -type f -print0 | xargs -0 sed -i s/mcpu=power8/mcpu=power9/
%endif
%endif

%pyproject_wheel -Csetup-args=-Dblas=flexiblas -Csetup-args=-Dlapack=lapack -Ccompile-args=-v

%install

%pyproject_install
pushd %{buildroot}%{_bindir} &> /dev/null
# Remove unversioned binaries
mv f2py f2py%{python3_pkgversion}
popd &> /dev/null

%if 0%{?fedora}
rm %{buildroot}%{python3_sitearch}/numpy/_core/include/numpy/random/libdivide.h
%endif

%check
%if %{with tests}
export PYTHONPATH=%{buildroot}%{python3_sitearch}
# test_ppc64_ibm_double_double128 is unnecessary now that ppc64le has switched long doubles to IEEE format.
# https://github.com/numpy/numpy/issues/21094
%ifarch %{ix86}
# Weird RuntimeWarnings on i686, similar to https://github.com/numpy/numpy/issues/13173
# Some tests also overflow on 32bit
%global ix86_k and not test_vector_matrix_values and not test_matrix_vector_values and not test_identityless_reduction_huge_array and not (TestKind and test_all)
%endif
%ifarch riscv64
# These two tests will always fail in RISC-V
# See https://github.com/numpy/numpy/pull/25246
# Patch from http://fedora.riscv.rocks:3000/rpms/numpy/commit/b34bc42e3455b5b070d96e041ef0a5303bdc8f6c
%global riscv64_k and not test_fpclass and not test_fp_noncontiguous and not (TestBoolCmp and test_float)
%endif
# test_deprecate_... fail on Python 3.13+ due to docstrings being dedented
# Upstream has removed the tests in git HEAD.
%if v"0%{python3_version}" >= v"3.13"
%global py313_k and not test_deprecate_help_indentation and not test_deprecate_preserve_whitespace
%endif
%ifnarch %{ix86}
%{__python3} runtests.py --no-build -- -ra -k 'not test_ppc64_ibm_double_double128 %{?ix86_k} %{?riscv64_k} %{?py313_k}' \
                                  -W "ignore:pkg_resources is deprecated as an API::pkg_resources"
%endif

%endif


%files -n python%{python3_pkgversion}-numpy
%license LICENSE.txt
%doc THANKS.txt
%{python3_sitearch}/%{modname}/__pycache__
%{_bindir}/numpy-config
%dir %{python3_sitearch}/%{modname}
%{python3_sitearch}/%{modname}/*.py*
%{python3_sitearch}/%{modname}/char
%{python3_sitearch}/%{modname}/ctypeslib
%{python3_sitearch}/%{modname}/core
%{python3_sitearch}/%{modname}/doc
%{python3_sitearch}/%{modname}/fft
%{python3_sitearch}/%{modname}/lib
%{python3_sitearch}/%{modname}/linalg
%{python3_sitearch}/%{modname}/ma
%{python3_sitearch}/%{modname}/random
%{python3_sitearch}/%{modname}/rec
%{python3_sitearch}/%{modname}/strings
%{python3_sitearch}/%{modname}/testing
%{python3_sitearch}/%{modname}/tests
%{python3_sitearch}/%{modname}/matrixlib
%{python3_sitearch}/%{modname}/polynomial
%{python3_sitearch}/%{modname}-*.dist-info
%{python3_sitearch}/%{modname}/__init__.pxd
%{python3_sitearch}/%{modname}/__init__.cython-30.pxd
%{python3_sitearch}/%{modname}/py.typed
%{python3_sitearch}/%{modname}/typing/
%{python3_sitearch}/%{modname}/_core/
%{python3_sitearch}/%{modname}/_pyinstaller/
%{python3_sitearch}/%{modname}/_typing/
%{python3_sitearch}/%{modname}/_utils/

%files -n python%{python3_pkgversion}-numpy-f2py
%{_bindir}/f2py%{python3_version}
%{python3_sitearch}/%{modname}/f2py


%changelog
* Tue Jul 07 2026 Charalampos Stratakis <cstratak@redhat.com> - 2.3.4-2
- Fix issues identified via Coverity static analysis
- Fix test_validate_transcendentals skip to match SVML dispatch
- Fix signed overflow issue in npy_gcd for INT_MIN on s390x
- Enable CET hardware protections
- Fixes: RHEL-137130, RHEL-161528, RHEL-160066, RHEL-238378

* Thu Oct 23 2025 Tomáš Hrnčiar <thrnciar@redhat.com> - 2.3.4-1
- Initial import
- Fedora contributions by:
      Benjamin A. Beasley <code@musicinmybrain.net>
      Bill Nottingham <notting@fedoraproject.org>
      Charalampos Stratakis <cstratak@redhat.com>
      Christian Dersch <lupinix@mailbox.org>
      Dan Horák <dan@danny.cz>
      David Malcolm <dmalcolm@redhat.com>
      David Tardon <dtardon@redhat.com>
      Deji Akingunola <deji@fedoraproject.org>
      Dennis Gilmore <dennis@ausil.us>
      dmalcolm <dmalcolm@fedoraproject.org>
      Elliott Sales de Andrade <quantum.analyst@gmail.com>
      Gwyn Ciesla <gwync@protonmail.com>
      Ignacio Vazquez-Abrams <ivazquez@fedoraproject.org>
      Iñaki Úcar <iucar@fedoraproject.org>
      Iryna Shcherbina <shcherbina.iryna@gmail.com>
      Jarod Wilson <jwilson@fedoraproject.org>
      Jaromir Capik <jcapik@redhat.com>
      Jef Spaleta <jspaleta@fedoraproject.org>
      Jerry James <loganjerry@gmail.com>
      Jesse Keating <jkeating@fedoraproject.org>
      Kalev Lember <klember@redhat.com>
      Karolina Surma <ksurma@redhat.com>
      Lukáš Zaoral <lzaoral@redhat.com>
      Lumir Balhar <lbalhar@redhat.com>
      Merlin Mathesius <mmathesi@redhat.com>
      Miro Hrončok <miro@hroncok.cz>
      Nikola Forró <nforro@redhat.com>
      Orion Poplawski <orion@nwra.com>
      Pavel Šimovec <psimovec@redhat.com>
      Peter Robinson <pbrobinson@gmail.com>
      Robert Kuska <rkuska@redhat.com>
      Scott Talbert <swt@techie.net>
      Simone Caronni <negativo17@gmail.com>
      Songsong Zhang <u2fsdgvkx1@gmail.com>
      Thomas Spura <thomas.spura@gmail.com>
      Tomáš Hrnčiar <thrnciar@redhat.com>
      Tomas Orsava <torsava@redhat.com>
      Tomas Tomecek <ttomecek@redhat.com>
      Tulio Magno Quites Machado Filho <tuliom@redhat.com>
      Ville Skyttä <scop@fedoraproject.org>
      Yaakov Selkowitz <yselkowi@redhat.com>

