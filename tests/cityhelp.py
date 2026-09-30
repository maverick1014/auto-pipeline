"""city-roles: a territory's governor is the live holder of its repo's main manager lock
(tests/test_agent_city_roles.py). A CityState test that wants a governor names it here instead of
writing lock files: CityState(..., main_fn=Mains({identity: sid})).
"""

import os


class Mains(dict):
    """identity -> sid of that territory's main manager; usable as CityState(main_fn=...).
    The pid is this test process (alive), so only the sid decides."""

    def __call__(self, identity):
        sid = self.get(identity)
        return (os.getpid(), sid) if sid else None


def lock_file(gitdir, sid, pid=None):
    """Write <gitdir>/agent_main.lock for SID (a server started as a process reads the file)."""
    os.makedirs(gitdir, exist_ok=True)
    with open(os.path.join(gitdir, "agent_main.lock"), "w") as fh:
        fh.write("%d 2026-09-30 10:00 %s -\n" % (os.getpid() if pid is None else pid, sid))
