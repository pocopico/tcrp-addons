#!/bin/bash
#
# Inject modules for getty
#
function load_fb_console() {
    echo "Loading FB and console modules..."
    for M in i915 efifb vesafb vga16fb; do
      [ -e /sys/class/graphics/fb0 ] && break
      /usr/sbin/modprobe ${M}
    done
}

if [ `mount | grep tmpRoot | wc -l` -gt 0 ] ; then
HASBOOTED="yes"
echo -n "System passed junior"
else
echo -n "System is booting"
HASBOOTED="no"
fi

if [ "$HASBOOTED" = "no" ]; then

    echo "extract cgetty.tgz to /usr/sbin/ "
    tar xfz /exts/cgetty/cgetty.tgz -C /

    TARGET_PLATFORM="$(uname -u | cut -d '_' -f2)"
    echo $TARGET_PLATFORM
    if [ "${TARGET_PLATFORM}" != "bromolow" ]; then
        load_fb_console
    fi

elif [ "$HASBOOTED" = "yes" ]; then
# run when boot installed DSM
  echo "Installing serial-getty service on installed DSM"
  cp -fv /tmpRoot/lib/systemd/system/serial-getty\@.service /tmpRoot/lib/systemd/system/getty\@.service
  sed -i 's|^ExecStart=.*|ExecStart=-/sbin/agetty %I 115200 linux|' /tmpRoot/lib/systemd/system/getty\@.service
  mkdir -vp /tmpRoot/lib/systemd/system/getty.target.wants
  ln -sfv /lib/systemd/system/getty\@.service /tmpRoot/lib/systemd/system/getty.target.wants/getty\@tty1.service
  echo -e "DSM mode\n" > /tmpRoot/etc/issue
  
  cp -fRv /usr/share/keymaps /tmpRoot/usr/share/
  cp -fv /usr/sbin/loadkeys /tmpRoot/usr/sbin/
  cp -fv /usr/sbin/setleds /tmpRoot/usr/sbin/
  DEST="/tmpRoot/lib/systemd/system/keymap.service"
  echo "[Unit]"                                                               > ${DEST}
  echo "Description=Configure keymap"                                         >>${DEST}
  echo "After=getty.target"                                                   >>${DEST}
  echo                                                                        >>${DEST}
  echo "[Service]"                                                            >>${DEST}
  echo "Type=oneshot"                                                         >>${DEST}
  echo "RemainAfterExit=true"                                                 >>${DEST}
  echo "ExecStart=/usr/sbin/loadkeys /usr/share/keymaps/i386/qwerty/us.map.gz" >>${DEST}
  echo                                                                        >>${DEST}
  echo "[Install]"                                                            >>${DEST}
  echo "WantedBy=multi-user.target"                                           >>${DEST}

  mkdir -p /tmpRoot/etc/systemd/system/multi-user.target.wants
  ln -sf /lib/systemd/system/keymap.service /tmpRoot/lib/systemd/system/multi-user.target.wants/keymap.service
fi
