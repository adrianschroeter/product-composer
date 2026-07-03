""" Package selection set

"""

from .PkgSelect import PkgSelect


class PkgSet:
    def __init__(self, name):
        self.name = name
        self.pkgs = []
        self.byname = None
        self.supportstatus = None
        self.override_supportstatus = False

    def _create_byname(self):
        byname = {}
        for sel in self.pkgs:
            name = sel.name
            if name not in byname:
                byname[name] = []
            byname[name].append(sel)
        self.byname = byname

    def _byname(self):
        if self.byname is None:
            self._create_byname()
        return self.byname

    @staticmethod
    def _apply_supportstatus(sel, supportstatus, supportstatus_forced):
        sel.supportstatus = supportstatus
        sel.supportstatus_forced = supportstatus_forced and supportstatus is not None

    def _merge_duplicate_supportstatus(self, existing, incoming):
        if existing.supportstatus_forced:
            return
        if incoming.supportstatus_forced:
            self._apply_supportstatus(existing, incoming.supportstatus, True)
            return
        if existing.supportstatus is None and incoming.supportstatus is not None:
            self._apply_supportstatus(existing, incoming.supportstatus, False)

    def add_specs(self, specs):
        for spec in specs:
            sel = PkgSelect(spec, supportstatus=self.supportstatus, supportstatus_forced=self.override_supportstatus)
            self.pkgs.append(sel)
        self.byname = None

    def add(self, other):
        indices = {sel: i for i, sel in enumerate(self.pkgs)}
        for sel in other.pkgs:
            idx = indices.get(sel)
            if idx is not None:
                # copy before mutating: the existing selector may be shared with a cached set
                existing = self.pkgs[idx].copy()
                self.pkgs[idx] = existing
                self._merge_duplicate_supportstatus(existing, sel)
                continue
            if self.override_supportstatus or (self.supportstatus is not None and sel.supportstatus is None):
                sel = sel.copy()
                self._apply_supportstatus(sel, self.supportstatus, self.override_supportstatus)
            indices[sel] = len(self.pkgs)
            self.pkgs.append(sel)
        self.byname = None

    def sub(self, other):
        otherbyname = other._byname()
        pkgs = []
        for sel in self.pkgs:
            name = sel.name
            if name not in otherbyname:
                pkgs.append(sel)
                continue
            for other_sel in otherbyname[name]:
                if sel is not None:
                    sel = sel.sub(other_sel)
            if sel is not None:
                pkgs.append(sel)
        self.pkgs = pkgs
        self.byname = None

    def intersect(self, other):
        otherbyname = other._byname()
        pkgs = []
        byisel = {}
        for sel in self.pkgs:
            name = sel.name
            if name not in otherbyname:
                continue
            for osel in otherbyname[name]:
                isel = sel.intersect(osel)
                if not isel:
                    continue
                existing = byisel.get(isel)
                if existing is not None:
                    self._merge_duplicate_supportstatus(existing, isel)
                else:
                    byisel[isel] = isel
                    pkgs.append(isel)
        self.pkgs = pkgs
        self.byname = None

    def matchespkg(self, arch, pkg):
        if self.byname is None:
            self._create_byname()
        if pkg.name not in self.byname:
            return False
        for sel in self.byname[pkg.name]:
            if sel.matchespkg(arch, pkg):
                return True
        return False

    def names(self):
        if self.byname is None:
            self._create_byname()
        return set(self.byname.keys())

    def __str__(self):
        return self.name + "(" + ", ".join(str(p) for p in self.pkgs) + ")"

    def __iter__(self):
        return iter(self.pkgs)

# vim: sw=4 et
