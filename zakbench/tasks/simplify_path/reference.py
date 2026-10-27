def solve(path):
    folders = []
    for part in path.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if folders:
                folders.pop()
            continue
        folders.append(part)
    return "/" + "/".join(folders)
