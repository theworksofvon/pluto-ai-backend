from connections import Connections


class SupabaseAdapter:
    def __init__(self):
        self.connections = Connections()
        self.supabase = self.connections.supabase

    def get_supabase_client(self):
        return self.supabase
