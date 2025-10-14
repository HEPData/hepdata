# HEPData Development Instructions

HEPData is a Python 3.9 Flask web application built on the Invenio v3 framework for managing high-energy physics research data. It provides a repository for experimental data from particle physics experiments.

**ALWAYS reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Prerequisites
Install these services before running HEPData locally:
- **PostgreSQL 14** database server
- **Redis** for caching
- **OpenSearch 2.18.0** for indexing and search
- **Node.js 18+** and npm for frontend assets
- **Python 3.9** (HEPData is ONLY compatible with Python 3.9, not 3.10+ or other versions)

### Docker-Based Development (Recommended)

**NEVER CANCEL builds or long-running commands. Docker builds take 10-20 minutes. Set timeout to 30+ minutes.**

1. **Setup environment variables:**
   ```bash
   export OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourPass123!
   export SAUCE_USERNAME=your_sauce_username  # Optional, for testing
   export SAUCE_ACCESS_KEY=your_sauce_key     # Optional, for testing
   ```

2. **Copy configuration:**
   ```bash
   cp hepdata/config_local.docker_compose.py hepdata/config_local.py
   ```

3. **Build and start containers:**
   ```bash
   docker-compose build  # NEVER CANCEL: Takes 10-20 minutes
   docker-compose up     # Starts all 6 services
   ```

4. **Initialize database (in another terminal):**
   ```bash
   docker-compose exec web bash -c "hepdata utils reindex -rc True"  # Ignore "hepsubmission" error
   docker-compose exec web bash -c "mkdir -p /code/tmp; ./scripts/initialise_db.sh your@email.com password"
   docker-compose exec db bash -c "psql hepdata -U hepdata -c 'update accounts_user set confirmed_at=NOW() where id=1;'"
   ```

5. **Access application:**
   - Open http://localhost:5000/
   - Login with your@email.com / password
   - **Note:** Initial loading may take several minutes for Celery to process sample records

### Local Development Setup

**Only use this if Docker is not available. Requires manual service installation.**

1. **Install Python 3.9 specifically:**
   ```bash
   # Ubuntu/Debian - you may need to add deadsnakes PPA for Python 3.9
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.9 python3.9-venv python3.9-dev
   ```

2. **Create virtual environment:**
   ```bash
   python3.9 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   ```

3. **Install dependencies:**
   ```bash
   pip install -e ".[all]" --upgrade -r requirements.txt  # NEVER CANCEL: Takes 5-10 minutes
   ```

4. **Verify PyYAML LibYAML bindings:**
   ```bash
   python -c "from yaml import CSafeLoader"  # Should not error
   ```

5. **Set environment variables:**
   ```bash
   export FLASK_ENV=development
   export FLASK_DEBUG=1
   export SQLALCHEMY_WARN_20=1
   ```

6. **Build frontend assets:**
   ```bash
   ./scripts/clean_assets.sh  # NEVER CANCEL: Takes 5-10 minutes
   ```

7. **Start services and initialize:**
   ```bash
   # Start PostgreSQL, Redis, OpenSearch first
   # Start Celery worker:
   celery -A hepdata.celery worker -l info -E -B -Q celery,priority,datacite

   # Initialize database:
   ./scripts/initialise_db.sh your@email.com password

   # Start web server:
   hepdata run --debugger --reload
   ```

## Testing

### Running Tests
```bash
# Unit tests only (no end-to-end):
pytest tests -k 'not e2e'  # NEVER CANCEL: Takes 10-15 minutes

# All tests (requires Sauce Labs credentials):
./run-tests.sh  # NEVER CANCEL: Takes 20-30 minutes
```

### Sauce Labs Setup (for end-to-end tests)
1. Set environment variables:
   ```bash
   export SAUCE_USERNAME=your_username
   export SAUCE_ACCESS_KEY=your_access_key
   export SAUCE_REGION=eu-central
   export SAUCE_TUNNEL_NAME=${SAUCE_USERNAME}_tunnel_name
   export SAUCE_PROXY_LOCALHOST=direct
   ```

2. For M1 MacBooks, also set:
   ```bash
   export SAUCE_OS=linux.aarch64
   ```

## Validation

### Build Validation
**ALWAYS run these steps after making changes:**

1. **Test Docker build:**
   ```bash
   docker-compose build web  # NEVER CANCEL: Takes 10-20 minutes
   ```

2. **Test assets build:**
   ```bash
   source venv/bin/activate
   hepdata webpack buildall  # NEVER CANCEL: Takes 5-10 minutes
   ```

3. **Run database migrations:**
   ```bash
   hepdata db init
   hepdata db create
   hepdata utils reindex -rc True
   ```

### End-to-End Validation Scenarios
**ALWAYS test these user scenarios after making changes:**

1. **User Registration and Login:**
   - Create new user account
   - Verify email confirmation (check terminal output in TESTING mode)
   - Login with credentials
   - Access user dashboard

2. **Data Submission Workflow:**
   - Navigate to submission page
   - Upload sample data file
   - Verify data parsing and validation
   - Check data conversion functionality

3. **Search Functionality:**
   - Use search box with various queries
   - Test filtering by dataset type
   - Verify OpenSearch integration working

4. **Data Export:**
   - Find existing record
   - Test different export formats (ROOT, CSV, YAML)
   - Verify file downloads correctly

### Pre-Development Validation Checklist
Before making code changes, verify your setup:

```bash
# 1. Check all services are accessible
curl -f http://localhost:5000/ || echo "Web server not running"
curl -f http://localhost:9200/ || echo "OpenSearch not running"
redis-cli ping || echo "Redis not running"

# 2. Verify Python environment
python --version | grep "3.9" || echo "Wrong Python version"
pip list | grep "invenio" || echo "HEPData not installed"

# 3. Check asset compilation works
hepdata webpack --help || echo "Webpack commands not available"

# 4. Verify database connectivity
docker-compose exec db psql hepdata -U hepdata -c "SELECT 1;" || echo "Database not accessible"
```

### Post-Change Validation Steps
After making changes:

```bash
# 1. Run linting (if available)
flake8 hepdata/ || echo "Linting not configured"

# 2. Run quick tests
pytest tests/ -k "not e2e" --maxfail=5 -x || echo "Unit tests failed"

# 3. Rebuild assets if frontend changes
hepdata webpack buildall

# 4. Test basic functionality
curl http://localhost:5000/api/status || echo "API not responding"
```

## Common Issues and Solutions

### Build Issues
- **Node.js SSL errors in Docker:** Use system Node.js installation instead of nodesource
- **Python version mismatch:** HEPData ONLY works with Python 3.9
- **PyYAML LibYAML binding missing:** Reinstall with LibYAML support
- **Webpack build failures:** Clear assets first with `./scripts/clean_assets.sh`

### Runtime Issues
- **Port 5000 conflict on macOS:** Disable AirPlay Receiver
- **Celery worker not processing:** Check Redis connection and restart worker
- **OpenSearch connection failed:** Verify OpenSearch is running on port 9200
- **Email links not working:** Set TESTING=False or use Mailpit

### Performance
- **Slow initial load:** Normal - Celery processes sample records on first run
- **Test timeouts:** Use appropriate timeout values, tests can take 20+ minutes

## Development Commands Reference

### Asset Management
```bash
hepdata collect -v                 # Collect static files
hepdata webpack clean             # Clean webpack bundles
hepdata webpack install --unsafe  # Install npm dependencies
hepdata webpack build            # Build production assets
hepdata webpack buildall         # Clean, install, and build
```

### Database Management
```bash
hepdata db init                   # Initialize database
hepdata db create                 # Create tables
hepdata db drop                   # Drop database
hepdata utils reindex -rc True    # Rebuild search index
```

### User Management
```bash
hepdata users create email@domain.com --password pass -a  # Create admin user
hepdata roles add email@domain.com coordinator            # Add coordinator role
hepdata roles add email@domain.com admin                 # Add admin role
```

## Repository Structure

### Key Directories
- `hepdata/` - Main application code
- `hepdata/modules/` - Feature modules (search, submission, etc.)
- `tests/` - Test suite including end-to-end tests
- `scripts/` - Build and utility scripts
- `docker/` - Docker configuration files
- `docs/` - Documentation source

### Important Files
- `requirements.txt` - Python dependencies
- `setup.py` - Package configuration and entry points
- `docker-compose.yml` - Local development services
- `Dockerfile` - Production container definition
- `hepdata/config.py` - Default configuration
- `hepdata/config_local.py` - Local overrides (create from examples)

### Configuration Files
- `hepdata/config_local.local.py` - Local development template
- `hepdata/config_local.docker_compose.py` - Docker development template
- `hepdata/config_local.gh.py` - GitHub Actions template

## Common File Operations

### View repository root
```
ls -la /
README.rst
INSTALL.rst
CONTRIBUTING.rst
setup.py
requirements.txt
docker-compose.yml
Dockerfile
run-tests.sh
scripts/
hepdata/
tests/
```

### Check package.json equivalent
The project uses `setup.py` instead of `package.json`:
```python
# Entry points include:
'console_scripts': ['hepdata = hepdata.cli:cli']
'invenio_assets.webpack': ['hepdata_theme_css = hepdata.modules.theme.webpack:theme']
```

### Important File Locations
```bash
# Configuration files (copy and modify as needed):
hepdata/config_local.local.py         # Local development template
hepdata/config_local.docker_compose.py # Docker template
hepdata/config_local.gh.py           # GitHub Actions template

# Key scripts:
scripts/initialise_db.sh             # Database setup
scripts/clean_assets.sh              # Asset rebuilding
run-tests.sh                         # Test runner

# Docker files:
Dockerfile                           # Main application container
docker-compose.yml                   # Development services
docker/db/Dockerfile                 # Database container

# Documentation:
docs/                                # Sphinx documentation
INSTALL.rst                          # Installation guide
CONTRIBUTING.rst                     # Contribution guidelines
```

### Environment Variables
Always set these for development:
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
export SQLALCHEMY_WARN_20=1
export OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourPassword123!
```

## CI/CD Information

The GitHub Actions workflow (`.github/workflows/ci.yml`):
- **NEVER CANCEL CI builds** - they take 20-30 minutes
- Tests against Python 3.9, PostgreSQL 14, OpenSearch 2.18.0
- Requires Sauce Labs credentials for end-to-end tests
- Builds and pushes Docker images on main branch
- **Always check CI status before merging**

## Time Expectations

**NEVER CANCEL these operations - use appropriate timeouts:**

- **Docker build:** 10-20 minutes (set 30+ minute timeout)
- **Pip install requirements:** 5-10 minutes (set 15+ minute timeout)
- **Webpack asset build:** 5-10 minutes (set 15+ minute timeout)
- **Unit tests:** 10-15 minutes (set 20+ minute timeout)
- **Full test suite:** 20-30 minutes (set 40+ minute timeout)
- **Database initialization:** 2-5 minutes (set 10+ minute timeout)
- **OpenSearch reindexing:** 2-5 minutes (set 10+ minute timeout)

## Troubleshooting Network Issues

If you encounter SSL/network issues:
1. Try Docker-based development instead of local
2. Use system package managers instead of downloading
3. Check if corporate proxy/firewall is blocking connections
4. For Node.js issues in Docker, modify Dockerfile to use apt-based Node.js installation
5. For pip install timeouts, increase timeout or try installing packages individually

### Known Docker Build Issues
The current Dockerfile may fail with SSL errors when downloading Node.js. Workaround:
```dockerfile
# Replace lines 22-26 with system Node.js installation:
RUN apt-get update && apt-get install -y nodejs npm
```

## Quick Reference Commands

### Check Application Status
```bash
# Check if services are running
docker-compose ps                    # Docker setup
curl http://localhost:5000/          # Web application
curl http://localhost:9200/          # OpenSearch
redis-cli ping                       # Redis (returns PONG)
```

### Common Git Operations
```bash
git status                           # Check working directory
git log --oneline -10               # Recent commits
git branch -a                       # All branches
```

### Directory Listing Commands
```bash
ls -la                               # Repository root contents
find . -name "*.py" | head -10      # Python files
find . -name "*.yml" -o -name "*.yaml" | head -5  # YAML configs
```

**Remember: This project requires patience - builds and tests take significant time but this is normal for a complex application with many dependencies.**
