{pkgs}: {
  deps = [
    pkgs.python312Packages.flake8
    pkgs.ruff
    pkgs.python312Packages.black
    pkgs.gh
    pkgs.rustc
    pkgs.pkg-config
    pkgs.openssl
    pkgs.libxcrypt
    pkgs.libiconv
    pkgs.cargo
    pkgs.mkdocs
  ];
}
