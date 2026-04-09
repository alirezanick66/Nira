import sys


class ImportLogger:
    """
    A meta path finder for tracking module imports.

    This class can be inserted into sys.meta_path to log every module import attempt.
    """

    def find_spec( self, fullname, path=None, target=None ):
        print( f"Module '{fullname}' is being imported  " )
        return None          # اجازه بده فرآیند عادی ادامه یابد


sys.meta_path.insert( 0, ImportLogger() )
