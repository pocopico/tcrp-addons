if [ $(cat /proc/cmdline 2>/dev/null | grep gettycon | wc -l) -gt 0 ]; then
  /usr/sbin/modprobe fbcon
  echo "Loading TCRP getty console - wait..." > /dev/tty1
  if [ "${MODEL}" = "dva1622" ]; then
    echo "Workaround for DVA1622..." > /dev/tty1
    echo > /dev/tty2
    /usr/sbin/ioctl /dev/tty0 22022 -v 2
    /usr/sbin/ioctl /dev/tty0 22022 -v 1
  fi
  /usr/sbin/loadkeys /usr/share/keymaps/i386/qwerty/us.map.gz  
  echo -e "Junior mode\n" > /etc/issue
  echo "Starting getty..."
  /usr/sbin/getty -L 0 tty1 &
fi
