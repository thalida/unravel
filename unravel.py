import textwrap
import parsel
import requests

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.validation import URL
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Footer, Input, Static, Switch, Label, Tree, Markdown


class UnravelApp(App):
    TITLE = "Unravel"
    SUB_TITLE = "A simple web page unraveler"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="n", action="new_search", description="New Search"),
    ]

    input_url = ""
    include_links = False

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="app"):
            with Container(id="app__input"):
                yield Input(
                    id="app__input__field",
                    placeholder="Enter a url...",
                    validators=[
                        URL("Please enter a valid URL"),
                    ],
                    valid_empty=True,
                )
                yield Label("", id="app__input__error", classes="hide")
                yield Horizontal(
                    Static("Include Link URLs:", id="app__input__switch-label"),
                    Switch(id="app__input__switch"),
                    id="app__input__switch-fieldset",
                )

            with Container(id="app__output", classes="hide"):
                with VerticalScroll(id="app__output__tree_pane"):
                    yield Tree("", id="tree")

                with Container(id="app__output__node_viewer"):
                    yield Markdown("", id="node")

        yield Footer()

    def action_new_search(self) -> None:
        input_el = self.query_one("#app__input__field")
        input_el.clear()
        input_el.focus()

    @on(Input.Changed)
    def on_input_change(self, event: Input.Changed) -> None:
        self.input_url = ""
        output_el = self.query_one("#app__output")
        output_el.add_class("hide")

        node_el = self.query_one("#node")
        node_el.update("")

        tree_el = self.query_one("#tree")
        tree_el.reset("", {})

        error_message_el = self.query_one("#app__input__error")
        error_message_el.update("")
        error_message_el.add_class("hide")

        if event.validation_result is None or event.validation_result.is_valid:
            return

        error_message_el.update(", ".join(event.validation_result.failure_descriptions))
        error_message_el.remove_class("hide")

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        if event.validation_result is None or not event.validation_result.is_valid:
            return

        self.input_url = event.value
        self.do_unravel()

    @on(Switch.Changed)
    def on_switch_change(self, event: Switch.Changed) -> None:
        self.include_links = event.value
        self.do_unravel()

    @on(Tree.NodeSelected)
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        node_el = self.query_one("#node")

        if node.data.get("is_root", False):
            markdown = textwrap.dedent(f"""
            # {node.data['source_url']}
            """)
        else:
            markdown = textwrap.dedent(f"""
            # {node.data["part"]}

            {node.data['protocol']}{node.data['path']}
            """)

        node_el.update(markdown)

    def do_unravel(self) -> None:
        if not self.input_url or len(self.input_url) == 0:
            return

        try:
            page = requests.get(self.input_url)
            page.raise_for_status()
        except requests.exceptions.RequestException:
            return

        selector = parsel.Selector(page.text)

        head_urls = selector.css("head").re(r"[\"\']((?:http[s]?://|//).+?)[\"\']")
        footer_urls = selector.css("footer").re(r"[\"\']((?:http[s]?://|//).+?)[\"\']")
        page_urls = selector.css("script::attr(src), link[rel=stylesheet]::attr(href)").extract()
        link_urls = selector.css("a::attr(href)").extract() if self.include_links else []

        all_urls = set(head_urls + footer_urls + page_urls + link_urls)
        external_urls = [url for url in all_urls if url.startswith("http") or url.startswith("//")]

        tree = self.query_one("#tree")
        tree.reset(self.input_url, {"is_root": True, "source_url": self.input_url})

        seen_nodes = {}
        for url in external_urls:
            protocol = url.split("//")[0]
            cleaned_url = url.replace("https://", "").replace("http://", "").replace("//", "")
            url_parts = cleaned_url.strip().rstrip("/").split("/")

            parent_node = tree.root
            for i in range(0, len(url_parts)):
                part = url_parts[i]
                path = "/".join(url_parts[: i + 1])
                is_leaf = i == len(url_parts) - 1

                node_data = {
                    "source_url": url,
                    "protocol": f"{protocol}//" if protocol.startswith("http") else "https://",
                    "path": path,
                    "part": part,
                    "is_leaf": is_leaf,
                }

                already_seen_path = path in seen_nodes.keys()

                if is_leaf:
                    if not already_seen_path:
                        seen_nodes[path] = parent_node.add_leaf(part, node_data)

                    continue

                if already_seen_path:
                    node_data = seen_nodes[path].data

                    # If we've already seen this path as a leaf node, we need to remove it and add it as a tree node
                    if node_data.get("is_leaf", False):
                        seen_nodes[path].remove()
                        seen_nodes[path] = parent_node.add(part, node_data)

                    parent_node = seen_nodes[path]
                    continue

                seen_nodes[path] = parent_node.add(part, node_data)
                parent_node = seen_nodes[path]

        tree.select_node(tree.root)
        tree.action_select_cursor()
        tree.root.expand()

        output_el = self.query_one("#app__output")
        output_el.remove_class("hide")
