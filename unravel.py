import textwrap
import parsel
import requests

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.validation import URL
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Input, Label, Tree, Markdown


class UnravelApp(App):
    TITLE = "Unravel"
    SUB_TITLE = "A simple web page unraveler"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding(key="N", action="new_search", description="New Search"),
    ]

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

        url = event.value
        page = requests.get(url)
        selector = parsel.Selector(page.text)

        page_urls = selector.css("script::attr(src), link[rel=stylesheet]::attr(href)").extract()
        external_urls = [url for url in page_urls if url.startswith("http") or url.startswith("//")]

        tree = self.query_one("#tree")
        tree.reset(url, {"is_root": True, "source_url": url})

        seen_nodes = {}
        for url in external_urls:
            protocol = url.split("//")[0]
            cleaned_url = url.replace("https://", "").replace("http://", "").replace("//", "")
            url_parts = cleaned_url.split("/")

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

                if is_leaf:
                    parent_node.add_leaf(part, node_data)
                    continue

                if path not in seen_nodes.keys():
                    seen_nodes[path] = parent_node.add(part, node_data)

                parent_node = seen_nodes[path]

        tree.select_node(tree.root)
        tree.action_select_cursor()

        output_el = self.query_one("#app__output")
        output_el.remove_class("hide")

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
