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

      show_resource: function (id, file_type, location) {
        if (file_type == 'html' && location.indexOf(".html") != -1 && location.indexOf('http') != 0) {
          $("#resource-detail").load('/record/resource/' + id, function () {
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
          });
        } else {
          if (HEPDATA.is_image(location)) {
            $("#resource-detail").html('<img src="' + location + '" width="400"/>');
          } else {

            var download_location = location;
            var file_name = 'Open Link';

            if (location.indexOf('http') == -1) {
              file_name = 'Download ' + location.substring(location.lastIndexOf('/') + 1);
              download_location = '/record/resource/' + id + '?view=true';
            }

            $("#resource-detail").html('<p>This is a link to an external resource which you can ' +
              'view by clicking the button below.</p><a href="' + download_location + '" ' +
              'class="btn btn-primary btn-large" target="_new">' + file_name + '</a>');
          }
        }
      },

      perform_upload_action: function (placement, form_name, colors, insertion_type) {



        var html = '<div id="upload-progress"></div>' +
          '<div><p>Uploading and validating files...</p></div>';
        if (insertion_type === 'large_area') {
          html = '<div id="upload-progress"></div>' +
            '<div style="width: 200px; margin: 0 auto;"><p>Uploading and validating files...</p></div>';
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
