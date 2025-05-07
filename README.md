# Sales Agent AI Assistant

An intelligent sales agent system built with Python that handles customer interactions, processes orders, and manages sales transactions. The system adapts to the customer's language and provides a seamless sales experience.

## 🎥 Demo

Watch our demo video showcasing the Sales Agent in action:

[![Sales Agent Demo](docs/demo.mp4)](docs/demo.mp4)

## 🚀 Quick Start

1. Clone the repository:

```bash
git clone https://github.com/josemartinrodriguezmortaloni/salesAgent.git
cd salesAgent
```

2. Create a virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

```

3. Install dependencies:

```bash
uv sync
```

4. Create a `.env` file with your configuration:

```env
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
MP_PUBLIC_KEY=your_mercadopago_public_key
MP_ACCESS_TOKEN=your_mercadopago_access_token
MP_WEBHOOK_URL=your_webhook_url
MP_DEV_WEBHOOK_URL=your_dev_webhook_url
MP_DEV_MODE=false
```

5. Run the application:

```bash
uv run .
```

## ✨ Features

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
- Payment processing:
  - Currently supports MercadoPago payment links
  - Additional payment methods planned for future implementation
- Automated sales reporting
- Product catalog management

### 🔄 Context Management

- Maintains conversation context across interactions
- Remembers customer preferences and order history
- Automatic cleanup of old contexts to optimize performance

## 📦 Dependencies

```txt
- mercadopago>=2.3.0: Payment processing
- openai-agents>=0.0.5: AI agent capabilities
- psycopg2-binary>=2.9.10: PostgreSQL database connection
- pydantic>=2.10.6: Data validation
- python-dateutil>=2.9.0.post0: Date handling
- python-dotenv>=1.0.1: Environment configuration
- rich>=13.9.4: Console output formatting
- supabase>=2.14.0: Database management
```

## 📁 Project Structure

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
├── docs/              # Documentation and demos
├── requirements.txt    # Project dependencies
└── README.md          # Project documentation
```

## 🚧 Features in Development

- [ ] WhatsApp Integration
  - Direct messaging support
  - Automated responses
  - Order tracking via WhatsApp
  - Payment notifications
- [ ] Admin Dashboard
  - Secure admin-only access
  - Sales analytics and reporting
  - Order management interface
  - Product catalog management
  - User management and permissions

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI for providing the AI capabilities
- Supabase for database infrastructure
