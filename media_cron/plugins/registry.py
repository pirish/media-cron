from media_cron.plugins.base import InputPlugin, LookupPlugin, OutputPlugin


class PluginRegistry:
    """Central registry holding available and configured plugins."""

    def __init__(self) -> None:
        self._inputs: dict[str, type[InputPlugin]] = {}
        self._lookups: dict[str, type[LookupPlugin]] = {}
        self._outputs: dict[str, type[OutputPlugin]] = {}

    def register_input(self, name: str, plugin_cls: type[InputPlugin]) -> None:
        self._inputs[name] = plugin_cls

    def register_lookup(self, name: str, plugin_cls: type[LookupPlugin]) -> None:
        self._lookups[name] = plugin_cls

    def register_output(self, name: str, plugin_cls: type[OutputPlugin]) -> None:
        self._outputs[name] = plugin_cls

    def get_input(self, name: str) -> InputPlugin:
        if name not in self._inputs:
            raise KeyError(f"Input plugin '{name}' not found in registry.")
        return self._inputs[name]()

    def get_lookup(self, name: str) -> LookupPlugin | None:
        if name not in self._lookups:
            return None
        return self._lookups[name]()

    def get_lookups(self, names: list[str] | None = None) -> list[LookupPlugin]:
        if names is None:
            return [cls() for cls in self._lookups.values()]
        results = []
        for name in names:
            if name in self._lookups:
                results.append(self._lookups[name]())
        return results

    def get_output(self, name: str) -> OutputPlugin | None:
        if name not in self._outputs:
            return None
        return self._outputs[name]()

    def get_outputs(self, names: list[str] | None = None) -> list[OutputPlugin]:
        if names is None:
            return [cls() for cls in self._outputs.values()]
        results = []
        for name in names:
            if name in self._outputs:
                results.append(self._outputs[name]())
        return results


# Global shared registry instance
default_registry = PluginRegistry()
