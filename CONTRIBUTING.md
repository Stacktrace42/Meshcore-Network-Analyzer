# Contributing to Meshcore Network Analyzer

Thank you for considering contributing to the Meshcore Network Analyzer! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, constructive, and professional in all interactions.

## Getting Started

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Meshcore-Network-Analyzer.git
   cd Meshcore-Network-Analyzer
   ```

2. **Set Up Environment**
   ```bash
   cp processing/.env.example processing/.env
   cp listener/.env.example listener/.env
   # Edit .env files with your configuration
   ```

3. **Build and Run**
   ```bash
   docker-compose -f docker-compose.build.yml up --build
   ```

4. **For Live Development** (with hot reload)
   ```bash
   docker-compose -f docker-compose.build.yml -f docker-compose.override.yml up
   ```

### Project Structure

```
Meshcore-Network-Analyzer/
├── processing/          # FastAPI backend service
│   ├── src/
│   │   ├── models.py    # SQLAlchemy database models
│   │   ├── schemas.py   # Pydantic request/response schemas
│   │   ├── api/         # API endpoint modules
│   │   ├── graph_builder.py      # Network graph construction
│   │   └── trace_scheduler.py    # Trace scheduling logic
│   ├── alembic/         # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── listener/            # Hardware listener service
│   ├── src/
│   │   ├── packet_listener.py    # Packet capture
│   │   ├── trace_handler.py      # Trace execution
│   │   └── api_client.py         # Backend communication
│   ├── requirements.txt
│   └── Dockerfile
├── visualization/       # React frontend
│   ├── src/
│   │   ├── pages/       # React page components
│   │   └── App.tsx      # Main application
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml   # Production deployment
```

## Development Guidelines

### Code Style

**Python (Backend/Listener)**
- Follow PEP 8
- Use type hints
- Docstrings for functions and classes
- Maximum line length: 100 characters

```python
def schedule_traces_for_week(self, week_number: int = None) -> None:
    """
    Schedule traces for all edges in the graph.

    Args:
        week_number: ISO week number (defaults to current week)
    """
```

**TypeScript (Frontend)**
- Follow standard TypeScript conventions
- Use functional components with hooks
- Prefer named exports
- Maximum line length: 100 characters

```typescript
interface TraceSchedule {
  id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  calculated_path?: string[]
}
```

### Git Workflow

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Atomic Commits**
   - Each commit should represent a single logical change
   - Write clear commit messages

   ```bash
   git commit -m "Add position triangulation for repeaters without GPS"
   ```

3. **Keep Branch Updated**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

4. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat: Add pagination to traces page

- Add offset/limit parameters to traces API
- Implement pagination controls in TracesPage
- Add page size selector (50/100/200)

Closes #42
```

## Database Changes

### Creating Migrations

1. **Modify Models**
   Edit `processing/src/models.py`

2. **Generate Migration**
   ```bash
   cd processing
   alembic revision --autogenerate -m "Description of changes"
   ```

3. **Review Generated Migration**
   Check `processing/alembic/versions/XXX_description.py`

4. **Test Migration**
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

### Migration Guidelines

- Always include both `upgrade()` and `downgrade()`
- Test migrations on a copy of production data
- Never edit existing migrations
- Add default values or allow NULL for new columns

## Testing

### Backend Tests
```bash
cd processing
pytest tests/
```

### Frontend Tests
```bash
cd visualization
npm test
```

### Manual Testing Checklist

- [ ] Map view loads and displays repeaters
- [ ] Edges render with correct SNR colors
- [ ] Estimated positions show in orange
- [ ] Trace scheduling creates new traces
- [ ] Configuration changes take effect
- [ ] Pagination works on traces page
- [ ] Dark/light mode switches correctly

## Pull Request Process

1. **Before Submitting**
   - Update documentation if needed
   - Add tests for new features
   - Ensure all tests pass
   - Verify Docker build succeeds

2. **PR Description Template**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   How to test these changes

   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-reviewed code
   - [ ] Commented complex code
   - [ ] Updated documentation
   - [ ] No new warnings
   - [ ] Added tests
   - [ ] Tests pass locally
   ```

3. **Review Process**
   - At least one approval required
   - Address all review comments
   - Keep discussion focused and professional
   - Be open to feedback

## Common Tasks

### Adding a New API Endpoint

1. Define schema in `processing/src/schemas.py`
2. Add endpoint in appropriate `processing/src/api/` module
3. Add authentication if needed (`Depends(require_admin)`)
4. Update frontend API client if needed
5. Test with Swagger UI at `/docs`

### Adding a New Configuration Value

1. Add to `system_config` table via migration
2. Update `_load_config()` in `trace_scheduler.py`
3. Add input field in `ConfigPage.tsx`
4. Test configuration update via web UI

### Modifying the Graph Algorithm

1. Edit `processing/src/graph_builder.py`
2. Add logging for debugging
3. Test with various path scenarios
4. Verify graph rebuilds correctly

## Documentation

- Update README.md for user-facing changes
- Update this file for contributor guidelines
- Add inline comments for complex logic
- Update API documentation in docstrings

## Questions?

- Open an issue for questions
- Check existing issues and PRs
- Review closed PRs for context

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
