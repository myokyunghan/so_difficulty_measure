# so_difficulty_measure

## Installation guide

### Instructions
1. Clone the repository:
   ```bash
   git clone https://github.com/myokyunghan/so_difficulty_measure.git
   cd so_difficulty_measure
   ```
2. Construct python virtual environment
    If you are mac user
    ```bash
    # in the 'so_difficulty_measure' directory
    brew install pyenv
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init --path)"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    source ~/.zshrc
    pyenv install 3.10.12
    pyenv versions
    ```

    If you are linux user,
    ```bash
    sudo apt install build-essential curl git libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev tk-dev
    curl https://pyenv.run | bash
    ```

    Edit your path to activate the pyenv
    
    ```bash
    # ~/.zshrc
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    eval "$(pyenv init -)"

    source ~/.zshrc
    pyenv install 3.10.12
    ```


3. Activate the virtual environment 
   ```bash
   # in the 'so_difficulty_measure' directory
   pyenv local 3.10.12
   python3 -m venv venv_so_difficulty_measure
   source venv_so_difficulty_measure/bin/activate
   ```
   
4. Install dependencies
   ```bash
    # in the 'so_difficulty_measure' directory
   pip install -r requirements.txt
   ```
   * Installation typically takes approximately 10-15 minutes on a standard desktop comuter, excluding GPU driver and CUDA installation.

5. Setting the path
    ```bash
   # in the 'so_difficulty_measure' directory
   pip install -e .
   ```


6. Setting the configuration of database
   you need to input the configuration of the database, which is located in `so_difficulty_measure/setting_for_sdm/config.py`

    ```python
   database_info={
   'host'      : "input ip adress for your database",
   'dbname'    : "input name for your database",
   'user'      : "input username for your database",
   'password'  : "input password for your database",
   'schema'    : "input schema for your database",
   }
   ```
