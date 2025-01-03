# General OS Setup and Hardening.

Hardening means the practice to aplly best practices to secure a server online, it is very
important to secure your server hosting your apps to avoid data lost or corruption.

!!! danger

    Accounting information is critical to any entity and if you want to host your accounting
    system by your self you should take any rasonable steps to secure you web server.

!!! warning 

    This guide is just a list of the minimal steps to secure your web server and it is not
    a exaustive or comprensible list, protec your server is your own responsability.

=== ":simple-ubuntu: APT Based OS"

    ### Keep the system up to date Debian based OS.

    ``` bash
    sudo apt update
    sudo apt upgrade -y
    ```

    ### Enable the firewall (Ubuntu UFW).

    ```
    sudo ufw enable
    sudo ufw allow ssh
    sudo ufw allow http
    sudo ufw allow https
    ```
    
    ### Add a sudo user.
    
    ```
    adduser serveradmin
    passwd serveradmin
    sudo usermod -aG sudo serveradmin
    ```
=== ":simple-fedora: RPM Based OS"

    ### Keep the system up to date Fedora based OS.

    Run as frecuently as posible.

    ```bash
    sudo dnf update -y 
    ```
    
    ### Add a sudo user.

    A sudo user will let you login to your system with out the user root, if you are using
    the Cockpit web console you can perfom administrative task with a sudo user.
    
    ```bash
    adduser serveradmin
    passwd serveradmin
    sudo usermod -aG sudo serveradmin
    ```

    !!! warning 

        Chosse a custom user name, avoid using predictable names, this way attacker will have
        the double task to guest your `user` and `password` to have access to your server, 
        a user name like `iamthemasterchief` it is more secure than a `admin` user.

    Only if you have a sudo user you can disable the remote root login via SSH editing the
    file `/etc/ssh/sshd_config` and set root login to not:

    ```
    PermitRootLogin no
    ```

    You must restart the SSH service with:

    ```bash
    sudo systemctl restart sshd
    ```
    