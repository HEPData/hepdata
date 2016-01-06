var inspire_ds = (function () {

    return {
        get_inspire_data: function (inspire_id, callback) {
            $.ajax({
                dataType: "json",
                url: '/inspire/search?id=' + inspire_id,
                method: 'GET',
                processData: false,
                cache: true,
                success: function (data) {
                    callback(data);
                }
            });
        },

        is_null: function(data) {
            return data.query.authors == null && data.query.abstract == null && data.query.journal == null && data.query.title[0] == null;
        },

        create_html_summary: function (data, html) {

            html += '<p class="inspire-title"><a href="http://inspirehep.net/record/' + data.id + '" target="_blank">' + data.query.title[0] + '</a><p>';

            if (data.query.authors && data.query.authors.length > 0) {
                html += '<p class="inspire-authors">' + data.query.authors[0].full_name + (data.query.authors.length > 1 ? " et al." : " ") + '</p>';
            }

            if (data.query.journal_info != '' && data.query.journal_info != null) {
                html += '<p class="inspire-journal">' + data.query.journal_info + '</p>';
            }

            html += '<p class="inspire-abstract">' + data.query.abstract + '</p><br/>';

            return html;
        },

        render_inspire_data: function (data) {
            var html = "";
            if (data.status == 'success') {
                $("#inspire-retrieve-progress").addClass("hidden");

                html = '<div class="alert alert-info">A preview of the publication (not everything is displayed).</div>';
                html = inspire_ds.create_html_summary(data, html);
                html += '<p style="font-weight: bolder;">If you\'re happy that ' +
                    'this is the correct INSPIRE Id, you just need to click ' +
                    'on \'confirm\'. If not, you can retrieve another record.</p>';

                $("#success").removeClass("hidden");
                $("#inspire-add-button").removeClass("hidden");

            } else if (data.status == 'exists') {
                html = '<div class="alert alert-danger">A ' +
                    '<a href="/record/ins"' + data.id + '" target="_blank">' +
                    'record</a> with this inspire id already exists in HEPData.' +
                    '</div>';
                html = inspire_ds.create_html_summary(data, html);

                $("#success").removeClass("hidden");
                $("#inspire-add-button").removeClass("hidden");

            }
            else {
                html = '<div class="alert alert-danger">An error occurred while trying to find the inspire record.</div>';
                $("#inspire-add-button").addClass("hidden");
            }

            $("#inspire-result").addClass("well well-sm");
            $("#inspire-result").html(html);
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        }
    }
})();