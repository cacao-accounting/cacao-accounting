{pkgs}: {
  deps = [
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
