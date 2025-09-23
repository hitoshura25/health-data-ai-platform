# Service Implementation Template

This template provides a starting point for implementing new services in the Health Data AI Platform.

## How to Use This Template

1. **Copy the template directory**:
   ```bash
   cp -r services/_template services/your-service-name
   cd services/your-service-name
   ```

2. **Rename and customize files**:
   - Update `README.md` with your service-specific information
   - Modify `requirements.txt` with your service dependencies
   - Customize `Dockerfile` for your service needs
   - Update `app/main.py` with your service logic
   - Add your tests in the `tests/` directory

3. **Update configuration**:
   - Add your service to `docker-compose.yml` in the root directory
   - Create a GitHub workflow file in `.github/workflows/your-service-name.yml`
   - Update the root `README.md` to include your service

## Template Structure

```
your-service-name/
├── README.md                 # Service documentation
├── requirements.txt          # Python dependencies
├── Dockerfile               # Docker container definition
├── .dockerignore           # Docker ignore file
├── app/                    # Application code
│   ├── __init__.py
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models
│   └── api/               # API routes (if applicable)
├── tests/                 # Test files
│   ├── __init__.py
│   ├── test_main.py      # Basic tests
│   └── conftest.py       # Test configuration
└── docs/                 # Service-specific documentation
    └── implementation_plan.md
```

## Dependencies

All services should use the shared components:

```python
# Add to your requirements.txt
-r ../../shared/requirements.txt
```

And import shared components:

```python
from shared.types import HealthDataProcessingMessage
from shared.validation import ValidationResult
from shared.common.logging import setup_logging
from shared.common.config import get_settings
```

## Development Workflow

1. **Implement your service** following the implementation plan
2. **Write tests** with good coverage
3. **Test locally** using Docker Compose
4. **Add CI/CD** workflow based on the template
5. **Update documentation** and deployment configs

## Service Types

Choose the appropriate template customizations based on your service type:

### FastAPI Web Service (Health API Service)
- Use FastAPI framework
- Include OpenAPI documentation
- Add authentication middleware
- Include health check endpoints

### Background Worker (Message Queue, ETL Engine)
- Use async/await patterns
- Include message processing logic
- Add proper error handling and retries
- Include monitoring and metrics

### ML Service (AI Query Interface)
- Include MLflow integration
- Add model loading and inference
- Include feature processing
- Add model performance monitoring

## Next Steps

1. Read your service's `implementation_plan.md` in the project planning directory
2. Follow the Test-Driven Development approach
3. Implement incrementally with frequent testing
4. Use the shared components and patterns
5. Add comprehensive logging and monitoring

## Need Help?

- Check existing implementation plans in the project root
- Review shared components in `shared/`
- Look at infrastructure setup in `docker-compose.yml`
- Check CI/CD examples in `.github/workflows/`