from src.models import Client, Order

def test_extreme_large_string_inputs():
    """Test that models can handle extremely large string inputs without crashing the memory allocation."""
    # 10 MB string
    huge_string = "A" * (10 * 1024 * 1024)
    
    # Create client with massive strings
    client = Client(
        id="123",
        name=huge_string,
        email=huge_string,
        social_link=huge_string,
        notes=huge_string,
        orders=[]
    )
    
    # Ensure it's stored correctly
    assert len(client.name) == 10 * 1024 * 1024
    
    # Create order with massive strings
    order = Order(
        id="order1",
        service_type=huge_string,
        price=100.0,
        currency="RUB",
        created_at=huge_string,
        deadline=huge_string,
        status=huge_string,
        files=[],
        payments=[]
    )
    
    client.orders.append(order)
    assert len(client.orders[0].service_type) == 10 * 1024 * 1024

def test_extreme_numerical_inputs():
    """Test extreme numerical inputs (very large floats)."""
    # Max float
    huge_float = 1.7976931348623157e+308
    
    order = Order(
        id="order1",
        service_type="Test",
        price=huge_float,
        currency="RUB",
        files=[],
        payments=[]
    )
    
    assert order.price == huge_float
    assert order.debt == huge_float
