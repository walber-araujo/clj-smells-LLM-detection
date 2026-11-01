## Metadata

* **Smell name:** Namespace Load Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `require`, `requiring-resolve`
* **Short explanation:** Dependencies should be explicitly declared within the `ns` form using `:require`.

```Clojure
(ns app.plugins.loader)

(defn start-plugin []
  (let [plugin-init (requiring-resolve 'app.plugins.custom/init)]
    (plugin-init)))
```
