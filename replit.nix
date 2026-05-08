{pkgs}: {
  deps = [
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
