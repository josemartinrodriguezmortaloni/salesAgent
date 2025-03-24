# Sales Agent AI Assistant

An intelligent sales agent system built with Python that handles customer interactions, processes orders, and manages sales transactions. The system adapts to the customer's language and provides a seamless sales experience.

## Features

### 🤖 Intelligent Agents

- **Main Agent**: Coordinates customer interactions and directs queries to specialized agents
- **Sales Agent**: Handles transactions, payments, and order processing
- **Product Agent**: Manages product information and inventory

### 🌍 Language Support

- Automatically detects and responds in the customer's language
- Maintains natural conversation flow
- Supports multiple languages seamlessly

### 💼 Sales Features

- Order management and tracking
- Multiple payment methods support:
  - Bank transfers
  - Cash payments
  - Card payments
- Automated sales reporting
- Product catalog management

### 🔄 Context Management

- Maintains conversation context across interactions
- Remembers customer preferences and order history
- Automatic cleanup of old contexts to optimize performance

## Dependencies

```txt
- openai-agents v0.0.5+: AI agent capabilities
- psycopg2-binary v2.9.10+: PostgreSQL database connection
- pydantic v2.10.6+: Data validation
- python-dateutil v2.9.0+: Date handling
- python-dotenv v1.0.1+: Environment configuration
- rich v13.9.4+: Console output formatting
- supabase v2.14.0+: Database management
```

## Setup

1. Clone the repository:

```bash
git clone https://github.com/josemartinrodriguezmortaloni/salesAgent.git
cd salesAgent
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your configuration:

```env
OPENAI_API_KEY=your_api_key_here
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

5. Run the application:

```bash
python __main__.py
```

## Project Structure

```
salesAgent/
├── __main__.py          # Application entry point
├── src/
│   ├── agents/         # AI agents implementation
│   │   ├── __init__.py
│   │   └── agents.py   # Agent definitions and logic
│   └── db/            # Database operations
│       ├── __init__.py
│       ├── database.py # Database functions
│       ├── models.py   # Data models
│       └── supabase_client.py # Supabase configuration
├── requirements.txt    # Project dependencies
└── README.md          # Project documentation
```

## Usage Examples

```python
# Initialize the chat context
context = ChatContext(uid=1)

# Example customer interaction
response = await agents.run("Quiero comprar 2 pizzas", context)
# Agent responds in Spanish: "¡Claro! He agregado 2 pizzas a tu orden..."

# English interaction
response = await agents.run("I want to buy 2 pizzas", context)
# Agent responds in English: "Sure! I've added 2 pizzas to your order..."
```

## Features in Development

- [ ] Enhanced product recommendations
- [ ] Integration with more payment providers
- [ ] Advanced analytics dashboard
- [ ] Customer loyalty system
- [ ] Multi-channel support

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the AI capabilities
- Supabase for database infrastructure
- LiveKit for real-time communication features
