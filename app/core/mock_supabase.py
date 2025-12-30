class MockSupabaseResponse:
    def __init__(self, data=None, user=None, session=None):
        self.data = data or []
        self.user = user
        self.session = session


class MockSupabaseBuilder:
    _storage = {
        "mac_address_bindings": [],
        "mac_verification_log": [],
        "profiles": [],
        "users": []
    }
    
    def __init__(self, table_name=None):
        self.table_name = table_name
        self._data = []
        self._operation = None
        self._insert_data = None
        self._update_data = None
        self._filters = []
        self._order_by = None
        self._limit_val = None
        self._range_start = None
        self._range_end = None
        self._return_inserted = False
        self._select_cols = "*"
    
    def select(self, *args, **kwargs):
        if not self._operation:
            self._operation = "select"
            select_str = args[0] if args else "*"
            if "!" in select_str:
                self._select_cols = select_str.split(",")[0].strip()
            else:
                self._select_cols = select_str
        else:
            self._return_inserted = True
        return self
    
    def eq(self, field, value):
        self._filters.append(("eq", field, value))
        return self
    
    def or_(self, *args, **kwargs):
        return self
    
    def order(self, field, desc=None):
        if desc is None:
            desc = False
        self._order_by = (field, desc)
        return self
    
    def limit(self, val):
        self._limit_val = val
        return self
    
    def range(self, start, end):
        self._range_start = start
        self._range_end = end
        return self
    
    def insert(self, data):
        self._operation = "insert"
        self._insert_data = data
        return self
    
    def update(self, data):
        self._operation = "update"
        self._update_data = data
        return self
    
    def execute(self):
        if self.table_name not in MockSupabaseBuilder._storage:
            MockSupabaseBuilder._storage[self.table_name] = []
        
        if self._operation == "insert":
            if self._insert_data:
                import uuid
                if "id" not in self._insert_data:
                    self._insert_data["id"] = str(uuid.uuid4())
                record = dict(self._insert_data)
                MockSupabaseBuilder._storage[self.table_name].append(record)
                return MockSupabaseResponse([record])
            return MockSupabaseResponse([])
        
        elif self._operation == "update":
            if self._filters and self._update_data:
                updated = []
                for record in MockSupabaseBuilder._storage[self.table_name]:
                    match = True
                    for op, field, value in self._filters:
                        if record.get(field) != value:
                            match = False
                            break
                    if match:
                        record.update(self._update_data)
                        updated.append(record)
                return MockSupabaseResponse(updated)
            return MockSupabaseResponse([])
        
        else:
            results = list(MockSupabaseBuilder._storage.get(self.table_name, []))
            
            for op, field, value in self._filters:
                results = [r for r in results if r.get(field) == value]
            
            if self._order_by:
                field, desc = self._order_by
                results = sorted(results, key=lambda x: x.get(field, ""), reverse=desc)
            
            if self._range_start is not None and self._range_end is not None:
                results = results[self._range_start:self._range_end + 1]
            elif self._limit_val:
                results = results[:self._limit_val]
            
            return MockSupabaseResponse(results)


class MockUser:
    def __init__(self, email):
        self.id = "mock-user-id-12345"
        self.email = email
        self.user_metadata = {}

class MockSession:
    def __init__(self):
        self.access_token = "mock-access-token-jwt"
        self.refresh_token = "mock-refresh-token"
        self.token_type = "bearer"

class MockSupabaseAuth:
    def sign_up(self, credentials):
        email = credentials.get("email")
        return MockSupabaseResponse(
            user=MockUser(email),
            session=MockSession()
        )
        
    def sign_in_with_password(self, credentials):
        email = credentials.get("email")
        return MockSupabaseResponse(
            user=MockUser(email),
            session=MockSession()
        )

class MockSupabaseClient:
    def __init__(self):
        self.auth = MockSupabaseAuth()

    def table(self, table_name: str):
        return MockSupabaseBuilder(table_name)
    
    def from_(self, table_name: str):
        return MockSupabaseBuilder(table_name)
