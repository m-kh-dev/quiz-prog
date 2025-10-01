import sys
import os
import json
from typing import Any, Dict, List, Callable, Optional, Union

# Third-party imports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QTabWidget, QSplitter, QMessageBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt, pyqtSlot, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
from PyQt5.QtWebChannel import QWebChannel

from bs4 import BeautifulSoup
import tinycss2


class JSBridge(QObject):
    """Bridge for communication between Python and JavaScript"""
    
    # Signal emitted when JavaScript calls a Python function
    js_call_python = pyqtSignal(str, list)
    
    def __init__(self, display_lib):
        super().__init__()
        self.display_lib = display_lib
        
    @pyqtSlot(str, list)
    def call_python_function(self, func_name: str, args: list):
        """Called from JavaScript to execute Python functions"""
        self.js_call_python.emit(func_name, args)
        
    @pyqtSlot(str, result=str)
    def get_constant(self, name: str) -> str:
        """Get constant value from JavaScript"""
        return json.dumps(self.display_lib.constants.get(name))
        
    @pyqtSlot(str, result=str)
    def get_variable(self, name: str) -> str:
        """Get variable value from JavaScript"""
        return json.dumps(self.display_lib.variables.get(name))
        
    @pyqtSlot(str, str)
    def set_variable(self, name: str, value: str):
        """Set variable value from JavaScript"""
        try:
            self.display_lib.variables[name] = json.loads(value)
        except:
            self.display_lib.variables[name] = value


class DisplayLib:
    """
    Main library for displaying pages and screens with CSS and JavaScript support
    """
    
    def __init__(self):
        self.constants = {}
        self.variables = {}
        self.methods = {}
        self.current_page = None
        self.js_bridge = None
        self.web_views = {}
        
    def define_constant(self, name: str, value: Any):
        """Define a constant that can be read from JavaScript"""
        self.constants[name] = value
        
    def define_variable(self, name: str, initial_value: Any = None):
        """Define a variable that can be read and written from both Python and JavaScript"""
        self.variables[name] = initial_value
        
    def define_method(self, name: str, method: Callable):
        """Define a method that can be called from JavaScript"""
        self.methods[name] = method
        
    def get_variable(self, name: str) -> Any:
        """Get the value of a variable"""
        return self.variables.get(name)
        
    def set_variable(self, name: str, value: Any):
        """Set the value of a variable"""
        self.variables[name] = value
        
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content using BeautifulSoup"""
        return BeautifulSoup(html_content, 'html.parser')
        
    def parse_css(self, css_content: str) -> List:
        """Parse CSS content using tinycss2"""
        return tinycss2.parse_stylesheet(css_content)
        
    def render_page(self, html_content: str, css_content: str = "", js_content: str = "") -> str:
        """Render a page with HTML, CSS, and JavaScript"""
        # Parse and process HTML
        soup = self.parse_html(html_content)
        
        # Add CSS if provided
        if css_content:
            style_tag = soup.new_tag('style')
            style_tag.string = css_content
            if soup.head:
                soup.head.append(style_tag)
            else:
                # Create head if it doesn't exist
                head_tag = soup.new_tag('head')
                head_tag.append(style_tag)
                if soup.html:
                    soup.html.insert(0, head_tag)
                else:
                    soup.insert(0, head_tag)
            
        # Add JavaScript bridge and initialization
        bridge_script = soup.new_tag('script')
        bridge_script.string = """
        // DisplayLib JavaScript Bridge
        if (typeof window.DisplayLib === 'undefined') {
            window.DisplayLib = {
                constants: {},
                variables: {},
                callPython: function(funcName, ...args) {
                    return new Promise((resolve, reject) => {
                        if (window.pyBridge) {
                            window.pyBridge.call_python_function(funcName, args);
                            // For simplicity, we'll resolve immediately
                            // In a real implementation, you'd handle async responses
                            resolve(null);
                        } else {
                            reject('Python bridge not available');
                        }
                    });
                },
                getConstant: function(name) {
                    if (window.pyBridge) {
                        const result = window.pyBridge.get_constant(name);
                        return result ? JSON.parse(result) : null;
                    }
                    return null;
                },
                getVariable: function(name) {
                    if (window.pyBridge) {
                        const result = window.pyBridge.get_variable(name);
                        return result ? JSON.parse(result) : null;
                    }
                    return null;
                },
                setVariable: function(name, value) {
                    if (window.pyBridge) {
                        window.pyBridge.set_variable(name, JSON.stringify(value));
                        return true;
                    }
                    return false;
                }
            };
            
            // Initialize when bridge is ready
            if (window.pyBridge) {
                // Load initial data
                setTimeout(() => {
                    if (typeof window.initDisplayLib === 'function') {
                        window.initDisplayLib();
                    }
                }, 100);
            }
        }
        """
        
        if soup.head:
            soup.head.append(bridge_script)
        else:
            head_tag = soup.new_tag('head')
            head_tag.append(bridge_script)
            if soup.html:
                soup.html.insert(0, head_tag)
            else:
                soup.insert(0, head_tag)
        
        # Add user JavaScript if provided
        if js_content:
            user_script = soup.new_tag('script')
            user_script.string = js_content
            if soup.body:
                soup.body.append(user_script)
            else:
                body_tag = soup.new_tag('body')
                body_tag.append(user_script)
                if soup.html:
                    soup.html.append(body_tag)
                else:
                    soup.append(body_tag)
        
        return str(soup)


class DisplayWindow(QMainWindow):
    """Main window for displaying web content"""
    
    def __init__(self, display_lib: DisplayLib):
        super().__init__()
        self.display_lib = display_lib
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('DisplayLib - Web Rendering Engine')
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Add a default tab
        self.add_browser_tab("Main Browser")
        
    def add_browser_tab(self, title: str) -> QWebEngineView:
        """Add a new browser tab"""
        # Create web view
        web_view = QWebEngineView()
        
        # Create JS bridge
        js_bridge = JSBridge(self.display_lib)
        self.display_lib.js_bridge = js_bridge
        
        # Create web channel for communication
        channel = QWebChannel()
        channel.registerObject('pyBridge', js_bridge)
        web_view.page().setWebChannel(channel)
        
        # Connect JavaScript to Python communication
        js_bridge.js_call_python.connect(self.handle_js_call)
        
        # Add to tabs
        self.tab_widget.addTab(web_view, title)
        self.display_lib.web_views[title] = web_view
        
        return web_view
        
    def handle_js_call(self, func_name: str, args: list):
        """Handle calls from JavaScript to Python"""
        if func_name in self.display_lib.methods:
            try:
                result = self.display_lib.methods[func_name](*args)
                print(f"JavaScript called Python function '{func_name}' with args {args}, result: {result}")
            except Exception as e:
                print(f"Error executing Python function '{func_name}': {e}")
        else:
            print(f"Unknown Python function called from JavaScript: {func_name}")
            
    def display_url(self, url: str, tab_title: str = "Main Browser"):
        """Display a URL in the specified tab"""
        if tab_title in self.display_lib.web_views:
            self.display_lib.web_views[tab_title].load(QUrl(url))
        else:
            web_view = self.add_browser_tab(tab_title)
            web_view.load(QUrl(url))
            
    def display_html(self, html_content: str, tab_title: str = "Main Browser"):
        """Display HTML content in the specified tab"""
        # Inject Qt WebChannel script
        webchannel_script = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pyBridge = channel.objects.pyBridge;
                // Initialize DisplayLib
                if (typeof window.initDisplayLib === 'function') {
                    window.initDisplayLib();
                }
            });
        });
        </script>
        """
        
        # Insert webchannel script into HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        if soup.head:
            soup.head.append(BeautifulSoup(webchannel_script, 'html.parser'))
        else:
            head = soup.new_tag('head')
            head.append(BeautifulSoup(webchannel_script, 'html.parser'))
            if soup.html:
                soup.html.insert(0, head)
            else:
                soup.insert(0, head)
                
        final_html = str(soup)
        
        if tab_title in self.display_lib.web_views:
            self.display_lib.web_views[tab_title].setHtml(final_html)
        else:
            web_view = self.add_browser_tab(tab_title)
            web_view.setHtml(final_html)


class DisplayLibDemo:
    """Demo application showcasing DisplayLib capabilities"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.display_lib = DisplayLib()
        self.window = DisplayWindow(self.display_lib)
        
        # Setup demo data and functionality
        self.setup_demo()
        
    def setup_demo(self):
        """Setup demo constants, variables, methods, and functions"""
        # Define constants
        self.display_lib.define_constant("APP_NAME", "DisplayLib Demo")
        self.display_lib.define_constant("VERSION", "1.0.0")
        self.display_lib.define_constant("MAX_ITEMS", 10)
        self.display_lib.define_constant("PI", 3.14159)
        
        # Define variables
        self.display_lib.define_variable("counter", 0)
        self.display_lib.define_variable("userName", "Guest")
        self.display_lib.define_variable("items", ["Item 1", "Item 2"])
        self.display_lib.define_variable("theme", "light")
        
        # Define methods (callable from JavaScript)
        self.display_lib.define_method("incrementCounter", self.increment_counter)
        self.display_lib.define_method("showMessage", self.show_message)
        self.display_lib.define_method("addItem", self.add_item)
        self.display_lib.define_method("getItems", self.get_items)
        self.display_lib.define_method("changeTheme", self.change_theme)
        
    def increment_counter(self, amount=1):
        """Python method to increment counter - callable from JavaScript"""
        current = self.display_lib.get_variable("counter")
        new_value = current + amount
        self.display_lib.set_variable("counter", new_value)
        print(f"Counter incremented by {amount}. New value: {new_value}")
        return new_value
        
    def show_message(self, message):
        """Python method to show a message - callable from JavaScript"""
        QMessageBox.information(self.window, "Message from JavaScript", message)
        return f"Message displayed: {message}"
        
    def add_item(self, item):
        """Python method to add an item - callable from JavaScript"""
        items = self.display_lib.get_variable("items")
        if len(items) < self.display_lib.constants["MAX_ITEMS"]:
            items.append(item)
            self.display_lib.set_variable("items", items)
            print(f"Item '{item}' added to list")
            return True
        print("Failed to add item: Maximum limit reached")
        return False
        
    def get_items(self):
        """Python method to get all items - callable from JavaScript"""
        return self.display_lib.get_variable("items")
    
    def change_theme(self, new_theme):
        """Python method to change theme - callable from JavaScript"""
        if new_theme in ["light", "dark"]:
            self.display_lib.set_variable("theme", new_theme)
            print(f"Theme changed to: {new_theme}")
            return True
        return False
        
    def run_demo(self):
        """Run the demo application"""
        # Display a demo page
        demo_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>DisplayLib Demo - Proper Bridge</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 20px; 
                    background-color: #f5f5f5;
                }
                .container { 
                    max-width: 800px; 
                    margin: 0 auto; 
                    background: white; 
                    padding: 20px; 
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 { color: #333; }
                .section { 
                    margin: 20px 0; 
                    padding: 15px; 
                    border: 1px solid #ddd; 
                    border-radius: 5px;
                }
                button { 
                    padding: 8px 15px; 
                    margin: 5px; 
                    background: #007acc; 
                    color: white; 
                    border: none; 
                    border-radius: 4px;
                    cursor: pointer;
                }
                button:hover { background: #005a9e; }
                .result { 
                    margin-top: 10px; 
                    padding: 10px; 
                    background: #f0f0f0; 
                    border-radius: 4px;
                }
                .dark-theme {
                    background-color: #333;
                    color: white;
                }
                .dark-theme .container {
                    background: #444;
                    color: white;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>DisplayLib Demo - Proper Bridge</h1>
                <p>This demo uses Qt WebChannel for proper Python-JavaScript communication.</p>
                
                <div class="section">
                    <h2>Constants from Python</h2>
                    <p>App Name: <span id="appName">Loading...</span></p>
                    <p>Version: <span id="version">Loading...</span></p>
                    <p>Max Items: <span id="maxItems">Loading...</span></p>
                    <p>PI: <span id="piValue">Loading...</span></p>
                </div>
                
                <div class="section">
                    <h2>Variables from Python</h2>
                    <p>Counter: <span id="counterValue">Loading...</span></p>
                    <p>User Name: <span id="userName">Loading...</span></p>
                    <p>Theme: <span id="currentTheme">Loading...</span></p>
                    <button onclick="incrementCounterHandler(1)">Increment Counter</button>
                    <button onclick="incrementCounterHandler(5)">Add 5</button>
                    <button onclick="resetCounter()">Reset Counter</button>
                    <button onclick="toggleTheme()">Toggle Theme</button>
                </div>
                
                <div class="section">
                    <h2>Items List</h2>
                    <ul id="itemsList"></ul>
                    <input type="text" id="newItem" placeholder="Enter new item">
                    <button onclick="addNewItem()">Add Item</button>
                </div>
                
                <div class="section">
                    <h2>Python Method Calls</h2>
                    <input type="text" id="messageInput" placeholder="Enter message">
                    <button onclick="showMessageHandler()">Show Message</button>
                </div>
                
                <div class="section">
                    <h2>JavaScript Execution Results</h2>
                    <div id="jsResults" class="result">Results will appear here</div>
                </div>
            </div>

            <script>
            // Initialize DisplayLib when bridge is ready
            window.initDisplayLib = function() {
                console.log("DisplayLib initialized with bridge");
                
                // Load and display constants
                document.getElementById('appName').textContent = DisplayLib.getConstant('APP_NAME') || 'Not found';
                document.getElementById('version').textContent = DisplayLib.getConstant('VERSION') || 'Not found';
                document.getElementById('maxItems').textContent = DisplayLib.getConstant('MAX_ITEMS') || 'Not found';
                document.getElementById('piValue').textContent = DisplayLib.getConstant('PI') || 'Not found';
                
                updateDisplays();
            };
            
            // Update variable displays
            function updateDisplays() {
                // Update from Python variables
                const counter = DisplayLib.getVariable('counter');
                const userName = DisplayLib.getVariable('userName');
                const theme = DisplayLib.getVariable('theme');
                const items = DisplayLib.getVariable('items');
                
                document.getElementById('counterValue').textContent = counter !== null ? counter : 'Error';
                document.getElementById('userName').textContent = userName !== null ? userName : 'Error';
                document.getElementById('currentTheme').textContent = theme !== null ? theme : 'Error';
                
                // Update items list
                const itemsList = document.getElementById('itemsList');
                itemsList.innerHTML = '';
                if (items && Array.isArray(items)) {
                    items.forEach(item => {
                        const li = document.createElement('li');
                        li.textContent = item;
                        itemsList.appendChild(li);
                    });
                }
                
                // Apply theme
                if (theme === 'dark') {
                    document.body.classList.add('dark-theme');
                } else {
                    document.body.classList.remove('dark-theme');
                }
            }
            
            // Increment counter function
            function incrementCounterHandler(amount) {
                DisplayLib.callPython('incrementCounter', amount).then(() => {
                    // Update display after Python operation
                    updateDisplays();
                    document.getElementById('jsResults').innerHTML = 
                        `<p>Counter incremented by ${amount}</p>`;
                }).catch(error => {
                    document.getElementById('jsResults').innerHTML = 
                        `<p>Error: ${error}</p>`;
                });
            }

            // Reset counter
            function resetCounter() {
                DisplayLib.setVariable('counter', 0);
                updateDisplays();
                document.getElementById('jsResults').innerHTML = 
                    `<p>Counter reset to 0</p>`;
            }

            // Toggle theme
            function toggleTheme() {
                const currentTheme = DisplayLib.getVariable('theme');
                const newTheme = currentTheme === 'light' ? 'dark' : 'light';
                DisplayLib.callPython('changeTheme', newTheme).then((success) => {
                    if (success) {
                        DisplayLib.setVariable('theme', newTheme);
                        updateDisplays();
                        document.getElementById('jsResults').innerHTML = 
                            `<p>Theme changed to: ${newTheme}</p>`;
                    }
                });
            }

            // Add new item
            function addNewItem() {
                const input = document.getElementById('newItem');
                const newItem = input.value.trim();
                if (newItem) {
                    DisplayLib.callPython('addItem', newItem).then((success) => {
                        if (success) {
                            input.value = '';
                            updateDisplays();
                            document.getElementById('jsResults').innerHTML = 
                                `<p>Item '${newItem}' added successfully</p>`;
                        } else {
                            document.getElementById('jsResults').innerHTML = 
                                `<p>Failed to add item: Maximum limit reached</p>`;
                        }
                    });
                }
            }

            // Show message
            function showMessageHandler() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                if (message) {
                    DisplayLib.callPython('showMessage', message).then((result) => {
                        document.getElementById('jsResults').innerHTML = 
                            `<p>${result}</p>`;
                        input.value = '';
                    });
                }
            }
            </script>
        </body>
        </html>
        """
        
        # Render and display the page
        rendered_html = self.display_lib.render_page(demo_html)
        self.window.display_html(rendered_html)
        
        # Show the window
        self.window.show()
        
        print("=== DisplayLib Demo ===")
        print("Using Qt WebChannel for Python-JavaScript communication")
        
        # Run the application
        return self.app.exec_()


def main():
    """Main function to run the DisplayLib demo"""
    demo = DisplayLibDemo()
    sys.exit(demo.run_demo())


if __name__ == "__main__":
    main()