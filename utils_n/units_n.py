from extensions_n import mysql

def get_units_tree():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT unit_id, unit_name, parent_id FROM units ORDER BY unit_name")
    rows = cursor.fetchall()
    tree = []
    lookup = {}
    units_dict = []
    for idx, row in enumerate(rows):
        units_dict.append({})
        units_dict[idx]["unit_id"] = row[0]
        units_dict[idx]["unit_name"] = row[1]
        units_dict[idx]["parent_id"] = row[2]
        units_dict[idx]["children"] = []
        # row["children"] = []
        lookup[row[0]] = units_dict[idx]

    for unit_dict in units_dict:
        if unit_dict["parent_id"] is None:
            tree.append(unit_dict)
        else:
            lookup[unit_dict["parent_id"]]["children"].append(unit_dict)
    return tree
