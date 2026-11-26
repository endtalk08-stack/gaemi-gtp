import os, pathlib, pwd, grp
p=pathlib.Path("/var/lib/gaemigtp-news")
st=p.stat()
print("JOB_UID=%s USER=%s GROUP=%s" % (os.getuid(),pwd.getpwuid(os.getuid()).pw_name,grp.getgrgid(os.getgid()).gr_name),flush=True)
print("DIR_UID=%s DIR_GID=%s MODE=%04o" % (st.st_uid,st.st_gid,st.st_mode & 0o777),flush=True)
print("DIR_WRITABLE_AS_SERVICE_USER=%s" % os.access(p,os.W_OK),flush=True)
