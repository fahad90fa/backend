class MockSupabaseResponse:
    def __init__(self, data=None):
        self.data = data or []


class MockSupabaseBuilder:
    def __init__(self):
        self._data = []
    
    def select(self, *args, **kwargs):
        return self
    
    def eq(self, *args, **kwargs):
        return self
    
    def or_(self, *args, **kwargs):
        return self
    
    def order(self, *args, **kwargs):
        return self
    
    def range(self, start, end):
        return self
    
    def insert(self, data):
        return self
    
    def update(self, data):
        return self
    
    def execute(self):
        return MockSupabaseResponse(self._data)


class MockSupabaseClient:
    def table(self, table_name: str):
        return MockSupabaseBuilder()
