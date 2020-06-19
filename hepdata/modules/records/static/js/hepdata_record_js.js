var hepdata_record = (function () {

    var preserve_abstract_line_wrap = function () {
      var abstract_html = $(".record-abstract-content").html();
      if (abstract_html) $(".record-abstract-content").html(abstract_html.trim());
    };

    var initialise_clipboard = function (selector) {
      new Clipboard(selector);
    };

    return {
      initialise: function () {
        MathJax.Hub.Config({
          tex2jax: {inlineMath: [['$', '$'], ['\\(', '\\)']]}
        });
        MathJax.Hub.Queue(["Typeset", MathJax.Hub]);

        preserve_abstract_line_wrap();
        initialise_clipboard('.copy-btn');
      },

      perform_upload_action: function (placement, form_name, colors, insertion_type) {
        var message = '<p>Uploading files...</p>'
        message += '<p>(Timeout after 60 seconds.)</p>'
        var html = '<div id="upload-progress"></div>' +
          '<div>' + message + '</div>';
        if (insertion_type === 'large_area') {
          html = '<div id="upload-progress"></div>' +
            '<div style="width: 200px; margin: 0 auto;"><p>' + message + '</p></div>';
        }

        $(".upload-form").css('display', 'none');

        $(placement).append(html);

        if (colors === undefined) {
          colors = ["#955BA5", "white"]
        }

        HEPDATA.render_loader("#upload-progress", [
            {x: 26, y: 30, color: colors[0]},
            {x: -60, y: 55, color: colors[1]},
            {x: 37, y: -10, color: colors[0]},
            {x: -60, y: 10, color: colors[0]},
            {x: -27, y: -30, color: colors[0]},
            {x: 60, y: -55, color: colors[1]}],
          {"width": 200, "height": 200}
        );

        document.forms[form_name].submit();

        return false;

      }
    }
  }
)();
