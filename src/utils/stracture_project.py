import os

EXCLUDE = { '.venv', '__pycache__', '.git', '.vscode' }


def tree( dir_path, prefix="" ):
    files = sorted( os.listdir( dir_path ) )
    files = [ f for f in files if f not in EXCLUDE ]

    for i, file in enumerate( files ):
        path = os.path.join( dir_path, file )
        connector = "└── " if i == len( files ) - 1 else "├── "
        print( prefix + connector + file )

        if os.path.isdir( path ):
            extension = "    " if i == len( files ) - 1 else "│   "
            tree( path, prefix + extension )


print( "\n" )
tree( "." )
